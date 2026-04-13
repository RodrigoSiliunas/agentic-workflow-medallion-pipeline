"""Channels routes — CRUD de instancias Omni (WhatsApp/Discord/Telegram).

Fluxo de criacao:
1. POST /channels recebe {name, channel}
2. Cria registro local OmniInstance com state=connecting
3. Chama OmniService.create_instance() — se falhar, marca state=failed
4. Salva omni_instance_id retornado
5. Retorna OmniInstanceResponse

Para WhatsApp, o cliente faz polling em GET /channels/{id}/qr ate receber
state=connected. Para Discord/Telegram, cliente chama POST /channels/{id}/connect
com o bot token.
"""

import base64
import io
import uuid
from datetime import UTC, datetime

import qrcode
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user
from app.database.session import get_db
from app.models.channel import OmniInstance
from app.models.company import Company
from app.schemas.channel import (
    ConnectChannelRequest,
    CreateChannelRequest,
    OmniInstanceResponse,
    QRCodeResponse,
)
from app.services.omni_service import OmniService

router = APIRouter()
logger = structlog.get_logger()


@router.get("", response_model=list[OmniInstanceResponse])
async def list_channels(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista instancias Omni da empresa."""
    result = await db.execute(
        select(OmniInstance)
        .where(OmniInstance.company_id == auth.company_id)
        .order_by(OmniInstance.created_at.desc())
    )
    instances = result.scalars().all()
    return [_serialize(i) for i in instances]


@router.post("", response_model=OmniInstanceResponse, status_code=201)
async def create_channel(
    data: CreateChannelRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cria instancia Omni e persiste metadata local."""
    company = await _get_company(db, auth.company_id)

    instance = OmniInstance(
        company_id=auth.company_id,
        name=data.name,
        channel=data.channel,
        state="connecting",
    )
    db.add(instance)
    await db.flush()

    omni = OmniService()
    try:
        result = await omni.create_instance(
            name=data.name,
            channel=data.channel,
            company_slug=company.slug,
        )
        omni_id = result.get("id") or result.get("instanceId")
        instance.omni_instance_id = omni_id
        instance.last_sync_at = datetime.now(UTC)
        instance.state = "connecting"

        # WhatsApp: iniciar conexao para gerar QR code
        if data.channel == "whatsapp" and omni_id:
            try:
                await omni.connect_instance(omni_id)
            except Exception as connect_exc:
                logger.warning("omni auto-connect failed", error=str(connect_exc))
    except Exception as exc:
        logger.warning("omni create_instance failed", error=str(exc), name=data.name)
        instance.state = "failed"
        instance.last_error = str(exc)[:500]

    await db.commit()
    await db.refresh(instance)
    return _serialize(instance)


@router.post("/{instance_id}/connect", response_model=OmniInstanceResponse)
async def connect_channel(
    instance_id: uuid.UUID,
    data: ConnectChannelRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Conecta instancia (passa token para Discord/Telegram)."""
    instance = await _load_owned(db, instance_id, auth.company_id)
    omni = OmniService()

    # Se nao tem omni_instance_id, tentar criar no Omni primeiro
    if not instance.omni_instance_id:
        company = await _get_company(db, auth.company_id)
        try:
            result = await omni.create_instance(
                name=instance.name, channel=instance.channel,
                company_slug=company.slug,
            )
            instance.omni_instance_id = result.get("id") or result.get("instanceId")
        except Exception as exc:
            logger.warning("omni create on connect failed", error=str(exc))
            instance.state = "failed"
            instance.last_error = str(exc)[:500]
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Falha ao criar instancia no Omni: {exc}",
            ) from exc

    try:
        await omni.connect_instance(instance.omni_instance_id, token=data.token)
        instance.state = "connected"
        instance.last_sync_at = datetime.now(UTC)
        instance.last_error = None
    except Exception as exc:
        logger.warning("omni connect failed", error=str(exc), instance_id=str(instance_id))
        instance.state = "failed"
        instance.last_error = str(exc)[:500]
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Falha ao conectar instancia no Omni: {exc}",
        ) from exc

    await db.commit()
    await db.refresh(instance)
    return _serialize(instance)


@router.get("/{instance_id}/qr", response_model=QRCodeResponse)
async def get_channel_qr(
    instance_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna QR code para WhatsApp pairing (polling-friendly)."""
    instance = await _load_owned(db, instance_id, auth.company_id)

    if instance.channel != "whatsapp":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR code so esta disponivel para WhatsApp",
        )
    if not instance.omni_instance_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Instancia ainda nao foi criada no Omni",
        )

    omni = OmniService()

    # Verificar status da instancia no Omni (pode ja estar conectada)
    try:
        inst_data = await omni.get_instance(instance.omni_instance_id)
        if inst_data.get("isActive"):
            instance.state = "connected"
            instance.last_sync_at = datetime.now(UTC)
            await db.commit()
            return QRCodeResponse(
                instance_id=str(instance_id),
                state="connected",
                qr_code=None,
                expires_at=None,
            )
    except Exception:
        pass  # Fallback: tentar buscar QR normalmente

    try:
        result = await omni.get_qr_code(instance.omni_instance_id)
    except Exception as exc:
        logger.warning("omni qr failed", error=str(exc), instance_id=str(instance_id))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Nao foi possivel obter QR code do Omni: {exc}",
        ) from exc

    # Se QR é null, instancia pode ja estar conectada
    raw_qr = result.get("qr") or result.get("qrCode") or result.get("code")
    if not raw_qr:
        instance.state = "connected"
        instance.last_sync_at = datetime.now(UTC)
        await db.commit()
        return QRCodeResponse(
            instance_id=str(instance_id),
            state="connected",
            qr_code=None,
            expires_at=None,
        )

    # Converter texto QR (protocolo WhatsApp) em imagem PNG base64
    qr_image_b64 = _qr_to_base64(raw_qr)

    return QRCodeResponse(
        instance_id=str(instance_id),
        state=instance.state,
        qr_code=qr_image_b64,
        expires_at=result.get("expiresAt"),
    )


@router.delete("/{instance_id}", status_code=204)
async def disconnect_channel(
    instance_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Desconecta instancia no Omni e marca como disconnected (soft delete)."""
    instance = await _load_owned(db, instance_id, auth.company_id)

    if instance.omni_instance_id:
        omni = OmniService()
        try:
            await omni.disconnect_instance(instance.omni_instance_id)
        except Exception as exc:
            logger.warning("omni disconnect failed", error=str(exc))
            instance.last_error = str(exc)[:500]

    instance.state = "disconnected"
    instance.last_sync_at = datetime.now(UTC)
    await db.commit()


def _qr_to_base64(text: str) -> str:
    """Gera imagem QR code PNG em base64 a partir do texto."""
    img = qrcode.make(text, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


async def _load_owned(
    db: AsyncSession, instance_id: uuid.UUID, company_id: uuid.UUID
) -> OmniInstance:
    result = await db.execute(
        select(OmniInstance).where(
            OmniInstance.id == instance_id,
            OmniInstance.company_id == company_id,
        )
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instancia nao encontrada",
        )
    return instance


async def _get_company(db: AsyncSession, company_id: uuid.UUID) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nao encontrada",
        )
    return company


def _serialize(instance: OmniInstance) -> dict:
    return {
        "id": str(instance.id),
        "omni_instance_id": instance.omni_instance_id,
        "name": instance.name,
        "channel": instance.channel,
        "state": instance.state,
        "last_sync_at": instance.last_sync_at,
        "last_error": instance.last_error,
        "created_at": instance.created_at,
        "updated_at": instance.updated_at,
    }
