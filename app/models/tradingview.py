from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TradingViewCompany(Base):
    """Модель для хранения информации о компаниях с TradingView"""
    
    __tablename__ = "tradingview_companies"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    link: Mapped[str] = mapped_column(String(255))
    image_url: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    tags: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<TradingViewCompany(ticker='{self.ticker}', company_name='{self.company_name}')>" 