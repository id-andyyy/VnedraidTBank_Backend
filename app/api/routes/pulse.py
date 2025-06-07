from fastapi import APIRouter, Depends, HTTPException
from tpulse import TinkoffPulse
from typing import Dict, List, Any, Optional

pulse_router = APIRouter()

# Создаем экземпляр TinkoffPulse при запуске
pulse_service = TinkoffPulse()


@pulse_router.get("/user/{username}", response_model=Dict[str, Any])
async def get_user_info(username: str):
    """
    Получить информацию о пользователе по имени пользователя
    """
    try:
        user_info = pulse_service.get_user_info(username)
        return user_info
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Пользователь не найден: {str(e)}")


@pulse_router.get("/user/{user_id}/posts", response_model=Dict[str, Any])
async def get_user_posts(user_id: str):
    """
    Получить все посты пользователя по ID
    """
    try:
        user_posts = pulse_service.get_posts_by_user_id(user_id)
        return user_posts
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Посты не найдены: {str(e)}")


@pulse_router.get("/ticker/{ticker}/posts", response_model=Dict[str, Any])
async def get_ticker_posts(ticker: str, limit: Optional[int] = 5):
    """
    Получить новости по тикеру с возможностью ограничения количества
    """
    try:
        ticker_posts = pulse_service.get_posts_by_ticker(ticker)
        # Ограничиваем количество возвращаемых новостей
        if limit and limit > 0:
            ticker_posts["items"] = ticker_posts["items"][:limit]
        return ticker_posts
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Новости по тикеру не найдены: {str(e)}") 