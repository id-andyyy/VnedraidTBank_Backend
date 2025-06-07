from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewsArticle(Base):
    """
    Модель для хранения обработанных и обогащенных новостей.
    """
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512), comment="Обобщенный заголовок новости")
    full_text: Mapped[str] = mapped_column(Text, comment="Полный, объединенный текст новости")
    summary: Mapped[str] = mapped_column(Text, comment="Краткое содержание статьи от LLM")
    is_positive: Mapped[bool] = mapped_column(Boolean, comment="Тональность новости (True - позитивная)")
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, comment="Определено ли как AI-генерированный контент")
    tags: Mapped[str] = mapped_column(String(500), nullable=True, comment="Теги, присвоенные LLM")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    tickers: Mapped[str] = mapped_column(
        String(500), nullable=True, comment="Тикеры, упомянутые в статье")

    def __repr__(self) -> str:
        return f"<NewsArticle(id={self.id}, title='{self.title[:50]}...')>"
