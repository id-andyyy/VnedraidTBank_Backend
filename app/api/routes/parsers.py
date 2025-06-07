import json
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict, Any, Callable, List
import logging

# Импортируем функции парсеров
from app.utils.parserRBC import get_news_data as rbc_parser
# Импортируем обработчик LLM и сессию БД
from app.api.routes.llm import generate_response_sync
from app.db.session import SessionLocal
from app.schemas.news import NewsArticleCreate
from app.models.news import NewsArticle

# Настройка логгера
logger = logging.getLogger(__name__)

# Создаем роутер
parsers_router = APIRouter()

# --- СПИСОК ТЕГОВ (перенесен сюда для централизации) ---
ALLOWED_TAGS = [
    "энергетика", "финансы", "технологии", "промышленность",
    "потребительский сектор", "инфраструктура", "сельское хозяйство",
    "здравоохранение", "недвижимость", "материалы", "телекоммуникации",
    "развлечения", "образование", "электронная коммерция"
]

# --- РЕЕСТР ПАРСЕРОВ ---
PARSERS_REGISTRY: Dict[str, Callable[[], List[Dict[str, str]]]] = {
    "rbc": rbc_parser,
    # Когда у вас появится новый парсер, например, vedomosti_parser,
    # вы просто добавите его сюда:
    # "vedomosti": vedomosti_parser,
}

def process_news_with_llm(raw_news: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Отправляет сырые новости в LLM для обработки.
    """
    if not raw_news:
        return []

    tags_str = ", ".join(ALLOWED_TAGS)
    raw_news_json = json.dumps(raw_news, ensure_ascii=False, indent=2)

    prompt = f"""
Ты — продвинутый AI-аналитик новостей. Твоя задача — обработать входящий JSON-массив новостных статей.

Вот твои шаги:
1. **Дедупликация**: Найди статьи с одинаковым смыслом.
2. **Агрегация**: Для каждой группы дубликатов создай одну общую статью. Уникальные статьи обрабатывай как группу из одного элемента.
3. **Анализ и Обогащение**: Для каждой итоговой статьи сгенерируй:
    - `title`: Новый, краткий и емкий заголовок, отражающий суть всех дубликатов.
    - `full_text`: Связный и подробный текст, объединяющий всю важную информацию из дубликатов без противоречий.
    - `summary`: Очень краткое содержание (2-3 предложения).
    - `is_positive`: Булево значение. `true`, если новость позитивная или нейтральная, `false` — если негативная.
    - `tags`: Массив из 1-3 самых релевантных тегов, выбранных СТРОГО из этого списка: [{tags_str}].

Важные правила:
- Если ни один тег из списка не подходит к статье, НЕ включай эту статью в итоговый результат.
- Твой ответ должен быть ТОЛЬКО JSON-массивом обработанных статей. Без лишних слов и комментариев.

Вот JSON с новостями для обработки:
{raw_news_json}
"""
    
    logger.info("Отправка запроса к LLM для обработки новостей...")
    llm_response_str = generate_response_sync(prompt)
    
    try:
        processed_news = json.loads(llm_response_str)
        logger.info(f"LLM успешно обработала и вернула {len(processed_news)} новостей.")
        return processed_news
    except json.JSONDecodeError:
        logger.error("Ошибка декодирования JSON ответа от LLM.", exc_info=True)
        return []


def run_all_parsers_and_process():
    """
    Выполняет все парсеры, обрабатывает новости через LLM и сохраняет в БД.
    """
    logger.info("Запуск парсинга и обработки новостей...")
    
    # 1. Сбор данных
    combined_news = []
    for name, parser_func in PARSERS_REGISTRY.items():
        try:
            news_items = parser_func()
            if news_items:
                # Преобразуем к формату, который ожидает LLM
                formatted_items = [{"title": item["title"], "full_text": item["full_text"]} for item in news_items]
                combined_news.extend(formatted_items)
        except Exception as e:
            logger.error(f"Ошибка парсера '{name}': {e}", exc_info=True)

    if not combined_news:
        logger.warning("Парсеры не вернули данных. Процесс завершен.")
        return

    # 2. Обработка через LLM
    processed_articles = process_news_with_llm(combined_news)

    if not processed_articles:
        logger.warning("LLM не вернула обработанных статей. Процесс завершен.")
        return
        
    # 3. Сохранение в БД
    db = SessionLocal()
    try:
        # Очищаем старые новости перед добавлением новых
        num_deleted = db.query(NewsArticle).delete()
        logger.info(f"Удалено {num_deleted} старых новостей из таблицы.")

        for article_data in processed_articles:
            # Преобразуем список тегов в строку
            if 'tags' in article_data and isinstance(article_data['tags'], list):
                article_data['tags'] = ', '.join(article_data['tags'])
            
            db_article = NewsArticleCreate(**article_data)
            db.add(NewsArticle(**db_article.dict()))

        db.commit()
        logger.info(f"Успешно сохранено {len(processed_articles)} новостей в базу данных.")
    except Exception as e:
        logger.error("Ошибка при сохранении новостей в БД.", exc_info=True)
        db.rollback()
    finally:
        db.close()


@parsers_router.post("/run", response_model=Dict[str, str], status_code=202)
async def run_all_parsers(background_tasks: BackgroundTasks):
    """
    Запускает ВСЕ парсеры, обрабатывает новости через LLM и сохраняет в БД.
    """
    background_tasks.add_task(run_all_parsers_and_process)
    return {"message": "Процесс парсинга и обработки новостей запущен в фоновом режиме."} 