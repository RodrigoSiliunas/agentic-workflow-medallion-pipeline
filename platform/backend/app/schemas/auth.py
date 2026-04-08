"""Schemas de auth (request/response)."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterCompanyRequest(BaseModel):
    company_name: str
    company_slug: str
    admin_name: str
    admin_email: EmailStr
    admin_password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "viewer"


class UpdateUserRoleRequest(BaseModel):
    role: str
