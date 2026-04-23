"""Auth routes: login, register-company, refresh, logout.

Seguranca de tokens:
- **access_token**: retornado no JSON body, frontend guarda em memoria (Pinia).
  Curta duração (15 min). Usado no header Authorization: Bearer.
- **refresh_token**: setado como cookie httpOnly (nunca acessivel via JS).
  Longa duracao (7 dias). Usado apenas no POST /auth/refresh.

Essa separacao protege o refresh_token de XSS — mesmo que um script malicioso
rode na pagina, so consegue roubar o access_token (15 min de vida). O refresh
token fica inacessivel ao JavaScript.
"""

import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    revoke_token,
    verify_password,
)
from app.database.session import get_db
from app.middleware.rate_limiter import rate_limit_auth
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterCompanyRequest,
    TokenResponse,
)

router = APIRouter()

_REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
_COOKIE_PATH = "/api/v1/auth"
# Em dev (HTTP) usamos secure=False. Em prod atras de HTTPS, trocar pra True.
_COOKIE_SECURE = not settings.DEBUG
_COOKIE_SAMESITE: str = "lax"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        path=_COOKIE_PATH,
        max_age=_COOKIE_MAX_AGE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, path=_COOKIE_PATH)


@router.post("/login", response_model=TokenResponse, dependencies=[rate_limit_auth])
async def login(
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas"
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario desativado")

    token_data = {"sub": str(user.id), "company_id": str(user.company_id), "role": user.role}
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access)


@router.post(
    "/register-company", response_model=TokenResponse, status_code=201,
    dependencies=[rate_limit_auth],
)
async def register_company(
    data: RegisterCompanyRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Cria empresa + usuario root. Usado no onboarding."""
    existing = await db.execute(select(Company).where(Company.slug == data.company_slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug ja existe")

    existing_user = await db.execute(select(User).where(User.email == data.admin_email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ja cadastrado")

    company = Company(name=data.company_name, slug=data.company_slug)
    db.add(company)
    await db.flush()

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
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(None, alias=_REFRESH_COOKIE),
):
    """Emite novos tokens usando o refresh_token do cookie httpOnly.

    Fallback: aceita refresh_token no body JSON pra backward compat com
    clientes que ainda usam o flow antigo.
    """
    token = refresh_token
    if not token:
        try:
            body = await request.json()
            token = body.get("refresh_token")
        except Exception:
            pass

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token nao encontrado (cookie ou body)",
        )

    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido"
        )

    user_result = await db.execute(
        select(User).where(User.id == uuid.UUID(payload["sub"]))
    )
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inativo ou removido"
        )

    token_data = {
        "sub": str(user.id),
        "company_id": str(user.company_id),
        "role": user.role,
    }
    # Revogar refresh token antigo antes de gerar novo
    revoke_token(token)
    access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    """Revoga tokens e limpa cookie httpOnly."""
    # Revogar refresh token
    old_refresh = request.cookies.get("refresh_token")
    if old_refresh:
        revoke_token(old_refresh)
    # Revogar access token (do header Authorization)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        revoke_token(auth_header[7:])
    _clear_refresh_cookie(response)
