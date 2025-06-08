from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import or_, and_
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
        tickers: Optional[List[str]] = Query(
            None, description="Фильтровать по списку тикеров"),
        tags: Optional[List[str]] = Query(
            None, description="Фильтровать по списку тегов"),
):
    """
    Получение списка новостей.
    """
    query = db.query(NewsArticle)
    all_conditions = []

    if filter and current_user:
        user_conditions = []

        user_interested_tags = [
            tag_name for field, tag_name in TAG_MAP.items() if getattr(current_user, field, -2) >= -1
        ]

        if user_interested_tags:
            user_conditions.append(
                or_(*[NewsArticle.tags.contains(tag) for tag in user_interested_tags]))

        if current_user.tickers:
            user_tickers = [ticker.strip()
                            for ticker in current_user.tickers.split(',')]
            user_conditions.append(
                or_(*[NewsArticle.tickers.contains(ticker) for ticker in user_tickers]))

        if user_conditions:
            all_conditions.append(or_(*user_conditions))

    if tickers:
        all_conditions.append(
            or_(*[NewsArticle.tickers.contains(ticker) for ticker in tickers]))

    if tags:
        all_conditions.append(
            or_(*[NewsArticle.tags.contains(tag) for tag in tags]))

    if all_conditions:
        query = query.filter(and_(*all_conditions))

    news_list = query.order_by(NewsArticle.created_at.desc()).limit(top).all()
    return news_list


@news_router.get(
    "/latest-24h",
    response_model=List[NewsArticleInDB],
    summary="Получить новости за последние 24 часа"
)
def get_latest_news_24h(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Возвращает список новостей, опубликованных за последние 24 часа.
    """
    time_24_hours_ago = datetime.utcnow() - timedelta(hours=24)

    latest_news = db.query(NewsArticle)\
        .filter(NewsArticle.created_at >= time_24_hours_ago)\
        .order_by(NewsArticle.created_at.desc())\
        .all()

    return latest_news


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
