from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.core.config import settings
from app.models.user import User
from app.schemas.user import User as UserSchema, UserCreate, Token, UserUpdate
from app.utils.security import create_access_token, verify_password
from app.utils.user import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_username,
    update_user,
)

auth_router = APIRouter()


@auth_router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate, db: Session = Depends(get_db)
) -> Any:
    """
    Регистрация нового пользователя.
    """
    # Проверяем, существует ли пользователь с таким email
    user = get_user_by_email(db, user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует",
        )
    
    # Проверяем, существует ли пользователь с таким username
    user = get_user_by_username(db, user_in.username)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем уже существует",
        )
    
    # Создаем пользователя
    user = create_user(db, user_in)
    
    return user


@auth_router.post("/login", response_model=Token)
def login(
    response: Response,
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Вход в систему с получением JWT токена.
    
    Примечание: В OAuth2PasswordRequestForm поле называется username, 
    но мы используем его для передачи email.
    """
    # Сначала пробуем найти пользователя по email
    user = get_user_by_email(db, form_data.username)
    
    # Если пользователь не найден по email, пробуем найти по имени пользователя
    if not user:
        user = get_user_by_username(db, form_data.username)
    
    # Если пользователь не найден или пароль неверный
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email/имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Проверяем, активен ли пользователь
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь неактивен",
        )
    
    # Создаем JWT токен
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    
    # Устанавливаем JWT в куки
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # Только по HTTPS
        samesite="none",  # Для кросс-доменных запросов
        max_age=int(access_token_expires.total_seconds()),
        path="/"
    )

    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.get("/me", response_model=UserSchema)
def get_my_profile(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Получение профиля текущего пользователя.
    """
    return current_user


@auth_router.put("/me", response_model=UserSchema)
def update_my_profile(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Обновление профиля текущего пользователя.
    """
    # Проверяем, не занят ли email, если он меняется
    if user_in.email and user_in.email != current_user.email:
        user = get_user_by_email(db, user_in.email)
        if user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует",
            )
    
    # Проверяем, не занят ли username, если он меняется
    if user_in.username and user_in.username != current_user.username:
        user = get_user_by_username(db, user_in.username)
        if user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким именем уже существует",
            )
    
    # Обновляем профиль
    user = update_user(db, current_user.id, user_in)
    
    return user


class InvestTokenUpdate(BaseModel):
    invest_token: str


@auth_router.put("/me/invest-token", response_model=UserSchema)
def update_invest_token(
    token_data: InvestTokenUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Обновление токена инвестиций пользователя.
    """
    user_update = UserUpdate(invest_token=token_data.invest_token)
    user = update_user(db, current_user.id, user_update)
    
    return user


class TelegramIdUpdate(BaseModel):
    telegram_id: str


@auth_router.put("/me/telegram-id", response_model=UserSchema)
def update_telegram_id(
    telegram_data: TelegramIdUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Обновление Telegram ID пользователя.
    """
    user_update = UserUpdate(telegram_id=telegram_data.telegram_id)
    user = update_user(db, current_user.id, user_update)
    
    return user

