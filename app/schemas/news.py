from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# Схема для возврата данных о новости
class NewsArticleSchema(BaseModel):
    id: int
    title: str
    full_text: str
    summary: str
    is_positive: bool
    tags: Optional[str] = None
    tickers: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True
