import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.constants import UserRole


class UserBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone_number: str | None = None
    site: str | None = None


class UserCreate(UserBase):
    role: UserRole
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone_number: str | None = None
    site: str | None = None
    is_active: bool | None = None
    role: UserRole | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: UserRole
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
