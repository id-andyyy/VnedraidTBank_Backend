from datetime import datetime
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    invest_token = Column(String, nullable=True)
    telegram_id = Column(String, nullable=True)
    tickers = Column(String(500), nullable=True,
                     comment="Тикеры, интересные пользователю")

    # Tags as integer fields for weighting
    tag_energy = Column(Integer, default=0,
                        server_default='0', comment="энергетика")
    tag_finance = Column(Integer, default=0,
                         server_default='0', comment="финансы")
    tag_tech = Column(Integer, default=0, server_default='0',
                      comment="технологии")
    tag_industry = Column(Integer, default=0,
                          server_default='0', comment="промышленность")
    tag_consumer_sector = Column(
        Integer, default=0, server_default='0', comment="потребительский сектор")
    tag_infrastructure = Column(
        Integer, default=0, server_default='0', comment="инфраструктура")
    tag_agriculture = Column(
        Integer, default=0, server_default='0', comment="сельское хозяйство")
    tag_healthcare = Column(
        Integer, default=0, server_default='0', comment="здравоохранение")
    tag_real_estate = Column(
        Integer, default=0, server_default='0', comment="недвижимость")
    tag_materials = Column(
        Integer, default=0, server_default='0', comment="материалы")
    tag_telecom = Column(Integer, default=0,
                         server_default='0', comment="телекоммуникации")
    tag_entertainment = Column(
        Integer, default=0, server_default='0', comment="развлечения")
    tag_education = Column(
        Integer, default=0, server_default='0', comment="образование")
    tag_ecommerce = Column(
        Integer, default=0, server_default='0', comment="электронная коммерция")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
