from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.params import Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.models import User
from app.models.news import NewsArticle
from app.schemas.news import NewsArticleInDB

news_router = APIRouter()

TAG_MAP = {
    "tag_energy": "энергетика",
    "tag_finance": "финансы",
    "tag_tech": "технологии",
    "tag_industry": "промышленность",
    "tag_consumer_sector": "потребительский сектор",
    "tag_infrastructure": "инфраструктура",
    "tag_agriculture": "сельское хозяйство",
    "tag_healthcare": "здравоохранение",
    "tag_real_estate": "недвижимость",
    "tag_materials": "материалы",
    "tag_telecom": "телекоммуникации",
    "tag_entertainment": "развлечения",
    "tag_education": "образование",
    "tag_ecommerce": "электронная коммерция"
}


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
            tag_name for field, tag_name in TAG_MAP.items() if getattr(current_user, field, -1) >= 0
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
