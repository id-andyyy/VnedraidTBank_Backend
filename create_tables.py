import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импортируем модели, чтобы они были доступны для создания таблиц
from app.db.base_models import Base
from app.db.session import engine


def main():
    logger.info("Создание таблиц в базе данных...")
    Base.metadata.create_all(bind=engine)
    logger.info("Таблицы успешно созданы!")


if __name__ == "__main__":
    main() 