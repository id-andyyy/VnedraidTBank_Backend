from typing import List, Optional

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette import status

from app.api.deps import get_db, get_current_active_user
from app.core.constants import TAG_MAP
from app.models import User
from app.models.news import NewsArticle
from app.schemas.news import NewsArticleInDB

news_router = APIRouter()


@news_router.get(
    "/",
    response_model=List[NewsArticleInDB]
)
def read_news(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        top: int = Query(10, ge=1,
                         description="Количество новостей для возврата"),
        filter: Optional[bool] = Query(
            None, description="Фильтровать новости по интересам пользователя"),
):
    """
    Получение списка новостей.
    """
    query = db.query(NewsArticle)

    if filter and current_user:
        conditions = []

        user_interested_tags = [
            tag_name for field, tag_name in TAG_MAP.items() if getattr(current_user, field, -2) >= -1
        ]

        if user_interested_tags:
            conditions.append(
                or_(*[NewsArticle.tags.contains(tag) for tag in user_interested_tags]))

        if current_user.tickers:
            user_tickers = [ticker.strip()
                            for ticker in current_user.tickers.split(',')]
            conditions.append(
                or_(*[NewsArticle.tickers.contains(ticker) for ticker in user_tickers]))

        if conditions:
            query = query.filter(or_(*conditions))

    news_list = query.order_by(NewsArticle.created_at.desc()).limit(top).all()
    return news_list


@news_router.get("/{news_id}", response_model=NewsArticleInDB, summary="Получить новость по ID")
def get_news_by_id(
    news_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Получает одну новостную статью по её уникальному идентификатору.
    """
    news_article = db.query(NewsArticle).filter(
        NewsArticle.id == news_id).first()
    if not news_article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Новость с ID {news_id} не найдена"
        )
    return news_article
