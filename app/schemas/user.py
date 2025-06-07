from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# Общие атрибуты
class UserBase(BaseModel):
    email: EmailStr
    username: str


# Схема для создания пользователя
class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    # Опциональные поля при создании пользователя
    invest_token: Optional[str] = None
    telegram_id: Optional[str] = None


# Схема для обновления пользователя
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    invest_token: Optional[str] = None
    telegram_id: Optional[str] = None


# Схема для входа
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# Схема для токена доступа
class Token(BaseModel):
    access_token: str
    token_type: str


# Схема для данных токена
class TokenData(BaseModel):
    user_id: Optional[UUID] = None


# Схема для возврата данных пользователя
class User(UserBase):
    id: UUID
    is_active: bool
    invest_token: Optional[str] = None
    telegram_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 