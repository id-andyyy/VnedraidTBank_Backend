from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional


class TradingViewCompanyBase(BaseModel):
    """
    Базовая схема для компании TradingView.
    Содержит поля, которые являются общими для создания и чтения.
    """
    ticker: str
    company_name: str
    link: HttpUrl
    description: Optional[str] = None
    tags: Optional[str] = None

    class Config:
        from_attributes = True


class TradingViewCompanyCreate(TradingViewCompanyBase):
    """
    Схема для создания новой записи о компании.
    Наследует все поля от базовой схемы.
    """
    pass


class TradingViewCompany(TradingViewCompanyBase):
    """
    Схема для чтения данных о компании из API.
    Включает все поля, которые должны быть возвращены клиенту.
    """
    id: int
    created_at: datetime 