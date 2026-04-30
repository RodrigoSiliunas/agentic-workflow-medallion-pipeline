"""Schemas de auth (request/response)."""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    # Disambigua email duplicado entre tenants. Opcional quando email
    # so existe em uma empresa; obrigatorio quando colide.
    company_slug: str | None = Field(
        default=None,
        min_length=2, max_length=50, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
    )


class RegisterCompanyRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=100)
    company_slug: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    admin_name: str = Field(..., min_length=2, max_length=100)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    # Pydantic v2 serializa UUID como str no JSON output automaticamente.
    id: uuid.UUID
    email: str
    name: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "viewer"


class UpdateUserRoleRequest(BaseModel):
    role: str
