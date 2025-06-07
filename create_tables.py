import logging
from sqlalchemy import inspect
from sqlalchemy.schema import CreateTable

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импортируем модели, чтобы они были доступны для создания таблиц
from app.db.base_models import Base
from app.db.session import engine

def get_existing_tables():
    """Получает список существующих таблиц в базе данных"""
    inspector = inspect(engine)
    return inspector.get_table_names()

def get_table_columns(table_name):
    """Получает список колонок для указанной таблицы"""
    inspector = inspect(engine)
    return [col['name'] for col in inspector.get_columns(table_name)]

def main():
    logger.info("Проверка и обновление структуры базы данных...")
    
    # Получаем существующие таблицы
    existing_tables = get_existing_tables()
    
    # Создаем все таблицы из метаданных
    Base.metadata.create_all(bind=engine)
    
    # Проверяем новые таблицы
    new_tables = [table for table in Base.metadata.tables.keys() 
                 if table not in existing_tables]
    
    if new_tables:
        logger.info(f"Добавлены новые таблицы: {', '.join(new_tables)}")
    
    # Проверяем изменения в существующих таблицах
    for table_name in existing_tables:
        if table_name in Base.metadata.tables:
            existing_columns = get_table_columns(table_name)
            model_columns = [col.name for col in Base.metadata.tables[table_name].columns]
            new_columns = [col for col in model_columns if col not in existing_columns]
            
            if new_columns:
                logger.info(f"В таблице {table_name} добавлены новые колонки: {', '.join(new_columns)}")
    
    logger.info("Структура базы данных успешно обновлена!")

if __name__ == "__main__":
    main()