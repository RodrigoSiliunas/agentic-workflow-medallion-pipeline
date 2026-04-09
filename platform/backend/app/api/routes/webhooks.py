"""Webhook routes — Omni + Pipeline events."""

import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.models.channel import ActiveSession, ChannelIdentity
from app.models.chat import Message
from app.models.pipeline import Pipeline
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.omni_service import OmniService
from app.services.slash_commands import SlashCommandHandler, is_slash_command

logger = structlog.get_logger()
router = APIRouter()


def verify_hmac(payload: bytes, signature: str, secret: str) -> bool:
    """Valida HMAC-SHA256 signature do webhook."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/omni")
async def webhook_omni(request: Request, db: AsyncSession = Depends(get_db)):
    """Recebe mensagens normalizadas do Omni.

    HMAC validation: header X-Webhook-Signature deve conter HMAC-SHA256.
    """
    # HMAC validation
    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    if settings.OMNI_WEBHOOK_SECRET and (
        not signature or not verify_hmac(body, signature, settings.OMNI_WEBHOOK_SECRET)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HMAC signature invalida",
        )

    payload = json.loads(body)
    logger.info("Webhook Omni recebido", event_type=payload.get("type"))

    # Extrair dados da mensagem
    message_content = payload.get("content", {})
    text = message_content.get("text", "")
    sender_id = payload.get("from", "")
    instance_id = payload.get("instanceId", "")

    if not text or not sender_id:
        return {"status": "ignored", "reason": "no text or sender"}

    # Resolver identidade do usuario
    identity_result = await db.execute(
        select(ChannelIdentity).where(ChannelIdentity.channel_user_id == sender_id)
    )
    identity = identity_result.scalar_one_or_none()

    if not identity:
        logger.warning("Identidade nao vinculada", sender_id=sender_id)
        # Responder pedindo para vincular conta
        omni = OmniService()
        await omni.send_message(
            instance_id, sender_id,
            "Ola! Para usar o agente, vincule sua conta em nosso site primeiro."
        )
        return {"status": "unlinked_user"}

    user_id = identity.user_id

    # Determinar empresa do usuario
    from app.models.user import User
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()
    company_id = user.company_id

    # Detectar canal
    channel = _detect_channel(instance_id, payload)

    # Verificar se e slash command
    if is_slash_command(text):
        handler = SlashCommandHandler(
            db=db, user_id=user_id, company_id=company_id, channel=channel
        )
        response_text = await handler.handle(text)

        # Enviar resposta via Omni
        omni = OmniService()
        await omni.send_message(instance_id, sender_id, response_text)
        return {"status": "command_processed"}

    # Mensagem normal — enviar para LLM
    session_result = await db.execute(
        select(ActiveSession).where(
            ActiveSession.user_id == user_id,
            ActiveSession.channel == channel,
        )
    )
    session = session_result.scalar_one_or_none()

    if not session or not session.active_thread_id:
        omni = OmniService()
        await omni.send_message(
            instance_id, sender_id,
            "Nenhum pipeline ativo. Use /resume [nome-do-pipeline] para comecar."
        )
        return {"status": "no_active_session"}

    # Obter pipeline
    pipeline_result = await db.execute(
        select(Pipeline).where(Pipeline.id == session.active_pipeline_id)
    )
    pipeline = pipeline_result.scalar_one()

    # Salvar mensagem do usuario
    user_msg = Message(
        thread_id=session.active_thread_id,
        role="user",
        content=text,
        channel=channel,
    )
    db.add(user_msg)
    await db.flush()

    # Processar com LLM
    orchestrator = LLMOrchestrator(db, company_id, user.name)

    # Carregar historico
    history_result = await db.execute(
        select(Message)
        .where(Message.thread_id == session.active_thread_id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in reversed(history_result.scalars().all())
        if m.role in ("user", "assistant")
    ]

    # Coletar resposta completa (sem streaming para canais externos)
    full_response = ""
    async for event in orchestrator.process_message(
        user_message=text,
        pipeline_job_id=pipeline.databricks_job_id or 0,
        conversation_history=history[:-1],
    ):
        if event["type"] == "token":
            full_response += event["content"]

    # Salvar resposta
    if full_response:
        assistant_msg = Message(
            thread_id=session.active_thread_id,
            role="assistant",
            content=full_response,
            channel=channel,
        )
        db.add(assistant_msg)
        await db.flush()

        # Enviar via Omni
        omni = OmniService()
        await omni.send_message(instance_id, sender_id, full_response)

    return {"status": "processed"}


@router.post("/pipeline")
async def webhook_pipeline(request: Request, db: AsyncSession = Depends(get_db)):
    """Recebe eventos do pipeline agent (agent_pre/agent_post).

    Permite notificacoes proativas para usuarios.
    """
    payload = await request.json()
    logger.info("Webhook Pipeline recebido", event=payload.get("event"))

    # TODO: implementar notificacoes proativas
    # Quando pipeline falha, notificar usuarios via canais ativos

    return {"status": "received", "event": payload.get("event")}


def _detect_channel(instance_id: str, payload: dict) -> str:
    """Detecta canal a partir do payload ou nome da instancia."""
    instance_name = payload.get("instanceName", "")
    if "whatsapp" in instance_name.lower():
        return "whatsapp"
    if "discord" in instance_name.lower():
        return "discord"
    if "telegram" in instance_name.lower():
        return "telegram"
    return "unknown"
