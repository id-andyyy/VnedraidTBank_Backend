from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.api.deps import get_db, get_current_active_user
from app.core.constants import TAG_MAP, FIELD_MAP
from app.models import User
from app.models.news import NewsArticle
from app.models.tradingview import TradingViewCompany
from app.schemas.users import UserInteractionRequest, AddTickerRequest

users_router = APIRouter()


@users_router.get("/me/tags", response_model=Dict[str, int], summary="Получить рейтинг тегов пользователя")
def get_user_tag_ratings(current_user: User = Depends(get_current_active_user)):
    """
    Возвращает словарь, где ключ - это название тега,
    а значение - его текущий рейтинг для пользователя.
    """
    ratings = {
        tag_name: getattr(current_user, field_name, 0)
        for field_name, tag_name in TAG_MAP.items()
    }
    return ratings


def _update_user_tags(user: User, news_article: NewsArticle, increment: int):
    if not news_article.tags:
        return

    article_tags = [tag.strip() for tag in news_article.tags.split(',')]

    for tag_name in article_tags:
        field_name = FIELD_MAP.get(tag_name)
        if field_name and hasattr(user, field_name):
            current_value = getattr(user, field_name)
            setattr(user, field_name, current_value + increment)


@users_router.post("/me/like", status_code=status.HTTP_200_OK, summary="Лайкнуть новость")
def like_news(
        like_request: UserInteractionRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    news_article = db.query(NewsArticle).filter(
        NewsArticle.id == like_request.news_id).first()
    if not news_article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="News article not found")

    _update_user_tags(current_user, news_article, 1)

    db.add(current_user)
    db.commit()
    return {"message": "Like processed successfully"}


@users_router.post("/me/dislike", status_code=status.HTTP_200_OK, summary="Дизлайкнуть новость")
def dislike_news(
        like_request: UserInteractionRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    news_article = db.query(NewsArticle).filter(
        NewsArticle.id == like_request.news_id).first()
    if not news_article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="News article not found")

    _update_user_tags(current_user, news_article, -1)

    db.add(current_user)
    db.commit()
    return {"message": "Dislike processed successfully"}


@users_router.post("/me/tickers", status_code=status.HTTP_200_OK, summary="Добавить тикер компании в избранное")
def add_ticker_to_favorites(
    request: AddTickerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Добавляет тикер компании в отслеживаемые пользователем.
    """
    company = db.query(TradingViewCompany).filter(
        TradingViewCompany.id == request.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    user_tickers_str = current_user.tickers or ""
    ticker_set = {t.strip() for t in user_tickers_str.split(',') if t.strip()}

    ticker_set.add(company.ticker)

    current_user.tickers = ", ".join(sorted(list(ticker_set)))
    db.commit()

    return {"tickers": current_user.tickers}


@users_router.get("/me/tickers", response_model=Dict[str, str], summary="Получить избранные тикеры пользователя")
def get_favorite_tickers(current_user: User = Depends(get_current_active_user)):
    """
    Возвращает строку с тикерами, отслеживаемыми пользователем.
    """
    return {"tickers": current_user.tickers or ""}


@users_router.delete("/me/tickers/{ticker}", status_code=status.HTTP_200_OK, summary="Удалить тикер из избранного")
def remove_ticker_from_favorites(
    ticker: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Удаляет тикер из строки отслеживаемых пользователем.
    """
    user_tickers_str = current_user.tickers or ""
    ticker_set = {t.strip() for t in user_tickers_str.split(',') if t.strip()}

    ticker_set.discard(ticker)

    current_user.tickers = ", ".join(sorted(list(ticker_set)))
    db.commit()

    return {"tickers": current_user.tickers}
