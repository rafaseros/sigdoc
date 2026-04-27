import re
from datetime import datetime

from pydantic import BaseModel, field_validator


class CreateUserRequest(BaseModel):
    email: str
    full_name: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Formato de correo electrónico inválido")
        return v.lower()


class UpdateUserRequest(BaseModel):
    email: str | None = None
    full_name: str | None = None
    is_active: bool | None = None
    bulk_generation_limit: int | None = None
    role: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ("admin", "template_creator", "document_generator"):
            raise ValueError(
                "El rol debe ser 'admin', 'template_creator' o 'document_generator'"
            )
        return v

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Formato de correo electrónico inválido")
        return v.lower()


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetPasswordByAdminRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    bulk_generation_limit: int | None = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    size: int
