"""Auth routes: login, register-company, refresh."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database.session import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterCompanyRequest,
    TokenResponse,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas"
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario desativado")

    token_data = {"sub": str(user.id), "company_id": str(user.company_id), "role": user.role}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/register-company", response_model=TokenResponse, status_code=201)
async def register_company(data: RegisterCompanyRequest, db: AsyncSession = Depends(get_db)):
    """Cria empresa + usuario root. Usado no onboarding."""
    # Verificar slug unico
    existing = await db.execute(select(Company).where(Company.slug == data.company_slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug ja existe")

    # Verificar email unico
    existing_user = await db.execute(select(User).where(User.email == data.admin_email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ja cadastrado")

    # Criar empresa
    company = Company(name=data.company_name, slug=data.company_slug)
    db.add(company)
    await db.flush()

    # Criar usuario root
    user = User(
        company_id=company.id,
        email=data.admin_email,
        password_hash=hash_password(data.admin_password),
        name=data.admin_name,
        role="root",
    )
    db.add(user)
    await db.flush()

    token_data = {"sub": str(user.id), "company_id": str(company.id), "role": "root"}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido"
        )

    token_data = {
        "sub": payload["sub"],
        "company_id": payload["company_id"],
        "role": payload["role"],
    }
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )
