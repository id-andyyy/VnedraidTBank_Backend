import logging
from sqlalchemy.orm import Session

from app.db.base_models import Base
from app.db.session import engine

logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    Инициализация базы данных - создание всех таблиц.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("База данных инициализирована")


def drop_db() -> None:
    """
    Удаление всех таблиц из базы данных.
    """
    Base.metadata.drop_all(bind=engine)
    logger.info("База данных очищена") 