from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


# Схема для возврата данных о новости
class NewsArticleBase(BaseModel):
    title: str
    full_text: str
    summary: str
    is_positive: bool
    is_ai_generated: bool
    tags: Optional[str] = None
    tickers: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True
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