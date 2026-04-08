"""Dependency injection — AuthContext e autenticacao."""

import uuid
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.database.session import get_db
from app.models.user import ROLE_HIERARCHY, ROLE_PERMISSIONS, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass
class AuthContext:
    """Contexto de autenticacao injetado em todas as rotas protegidas."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    email: str
    name: str
    role: str
    permissions: list[str] = field(default_factory=list)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_role_or_above(self, role: str) -> bool:
        return ROLE_HIERARCHY.get(self.role, 0) >= ROLE_HIERARCHY.get(role, 0)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Extrai e valida o usuario do JWT token."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inativo")

    return AuthContext(
        user_id=user.id,
        company_id=user.company_id,
        email=user.email,
        name=user.name,
        role=user.role,
        permissions=ROLE_PERMISSIONS.get(user.role, []),
    )


def require_permission(permission: str):
    """Dependency que verifica se o usuario tem a permissao."""

    async def _check(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not auth.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissao necessaria: {permission}",
            )
        return auth

    return _check


def require_role(role: str):
    """Dependency que verifica se o usuario tem o role ou superior."""

    async def _check(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not auth.has_role_or_above(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role necessario: {role} ou superior",
            )
        return auth

    return _check
