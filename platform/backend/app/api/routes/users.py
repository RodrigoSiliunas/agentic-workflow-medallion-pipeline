"""User management routes (admin cria, gerencia)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user, require_permission
from app.core.security import hash_password
from app.database.session import get_db
from app.models.user import ROLE_HIERARCHY, User
from app.schemas.auth import CreateUserRequest, UpdateUserRoleRequest, UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna o usuario autenticado a partir do JWT (perfil completo do DB)."""
    result = await db.execute(select(User).where(User.id == auth.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")
    return user


@router.get("", response_model=list[UserResponse])
async def list_users(
    auth: AuthContext = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.company_id == auth.company_id).order_by(User.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: CreateUserRequest,
    auth: AuthContext = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db),
):
    # Nao pode criar usuario com role superior ao seu
    if ROLE_HIERARCHY.get(data.role, 0) >= ROLE_HIERARCHY.get(auth.role, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nao pode criar usuario com role igual ou superior ao seu",
        )

    # Email unico
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ja cadastrado")

    user = User(
        company_id=auth.company_id,
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        role=data.role,
    )
    db.add(user)
    await db.flush()
    return user


@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    data: UpdateUserRoleRequest,
    auth: AuthContext = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id, User.company_id == auth.company_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    if ROLE_HIERARCHY.get(data.role, 0) >= ROLE_HIERARCHY.get(auth.role, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nao pode atribuir role igual ou superior ao seu",
        )

    user.role = data.role
    await db.flush()
    return user
