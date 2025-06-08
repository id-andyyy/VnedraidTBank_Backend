from typing import Generator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.utils.security import verify_token

# Кастомная схема для получения токена из HttpOnly cookie


class OAuth2PasswordBearerWithCookie(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        # Сначала ищем токен в cookie 'access_token'
        token = request.cookies.get("access_token")
        if token:
            return token

        # Если в cookie нет, пробуем стандартный способ (из заголовка)
        # Это полезно для API-клиентов или тестов
        try:
            return await super().__call__(request)
        except HTTPException as e:
            # Игнорируем ошибку, если токен не найден в заголовке,
            # но возбуждаем, если он есть, но некорректный
            if e.status_code == status.HTTP_401_UNAUTHORIZED and e.detail == "Not authenticated":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from e
            raise


# Используем нашу кастомную схему
oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="/api/auth/login")


def get_db() -> Generator[Session, None, None]:
    """
    Зависимость для получения сессии базы данных.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Зависимость для получения текущего пользователя по токену.
    """
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Зависимость для получения активного пользователя.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    return current_user
