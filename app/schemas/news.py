from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class NewsArticleBase(BaseModel):
    """
    Базовая схема для новостной статьи.
    """
    title: str
    full_text: str
    summary: str
    is_positive: bool
    tags: Optional[str] = None

    class Config:
        from_attributes = True


class NewsArticleCreate(NewsArticleBase):
    """
    Схема для создания новой статьи в базе данных.
    """
    pass


class NewsArticleInDB(NewsArticleBase):
    """
    Схема для чтения статьи из базы данных, включая ID.
    """
    id: int
    created_at: datetime 