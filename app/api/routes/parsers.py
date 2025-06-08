import json
import os
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict, Any, Callable, List
import logging

# Импортируем функции парсеров
from app.utils.parserRBC import get_news_data as rbc_parser
from app.utils.parserKommersant import get_news_data as kommersant_parser
from app.utils.parserTradingView import get_news_data as tradingview_parser
# Импортируем обработчик LLM
from app.api.routes.llm import generate_response_sync
# Импортируем модели и схемы для работы с БД
from app.db.session import SessionLocal
from app.schemas.news import NewsArticleCreate, RawNewsCreate
from app.models.news import NewsArticle, RawNews
# Импортируем функцию дедупликации
from NoDuplicates import deduplicate_news_with_annoy

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
    "kommersant": kommersant_parser,
    "tradingview": tradingview_parser,
    # Когда у вас появится новый парсер, например, vedomosti_parser,
    # вы просто добавите его сюда:
    # "vedomosti": vedomosti_parser,
}

# Зависимость для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_duplicate_in_raw_news(title: str, full_text: str, db_session) -> bool:
    """
    Проверяет, есть ли уже такая новость в таблице сырых новостей.
    Сравнивает название (буква в букву) и первые 20 символов описания.
    
    Args:
        title: Заголовок новости
        full_text: Полный текст новости
        db_session: Сессия базы данных
    
    Returns:
        True если дубликат найден, False если новость уникальна
    """
    try:
        # Получаем первые 20 символов описания
        text_prefix = full_text[:20] if full_text else ""
        
        # Ищем в БД новости с точно таким же заголовком
        existing_news = db_session.query(RawNews).filter(
            RawNews.title == title
        ).all()
        
        # Если нашли новости с таким заголовком, проверяем первые 20 символов
        for news in existing_news:
            existing_text_prefix = news.full_text[:20] if news.full_text else ""
            if existing_text_prefix == text_prefix:
                logger.info(f"Найден дубликат в сырых новостях: '{title[:50]}...'")
                return True
        
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке дубликатов: {e}")
        return False

def save_raw_news_to_db(title: str, full_text: str, source: str, db_session) -> bool:
    """
    Сохраняет сырую новость в базу данных.
    
    Args:
        title: Заголовок новости
        full_text: Полный текст новости  
        source: Источник новости
        db_session: Сессия базы данных
    
    Returns:
        True если сохранение успешно, False если ошибка
    """
    try:
        raw_news = RawNews(
            title=title,
            full_text=full_text,
            source=source
        )
        
        db_session.add(raw_news)
        db_session.commit()
        logger.info(f"Сырая новость сохранена в БД: '{title[:50]}...' из источника '{source}'")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении сырой новости: {e}")
        db_session.rollback()
        return False

def process_single_news_with_llm(news_item: Dict[str, str]) -> Dict[str, Any]:
    """
    Отправляет одну новость в LLM для обработки и проверки на AI-генерацию.
    """
    if not news_item:
        return None

    tags_str = ", ".join(ALLOWED_TAGS)
    
    prompt = f"""
Ты — продвинутый AI-аналитик новостей. Твоя задача — обработать одну новостную статью и определить, была ли она сгенерирована AI.

Для данной статьи сгенерируй:
- `title`: Новый, краткий и емкий заголовок, отражающий суть статьи.
- `full_text`: Связный и подробный текст, сохраняющий всю важную информацию из оригинала.
- `summary`: Очень краткое содержание (2-3 предложения).
- `is_positive`: Булево значение. `true`, если новость позитивная или нейтральная, `false` — если негативная.
- `is_ai_generated`: Булево значение. Проанализируй ИСХОДНЫЙ текст статьи на предмет AI-генерации, используя следующие критерии:
  * Лингвистические паттерны: повторяющиеся фразы, чрезмерно формальный или общий язык
  * Структурная согласованность: неестественная связность, резкие смены тем
  * Контекстная глубина: наличие оригинальных инсайтов или опора на общие знания
  * Стилистические маркеры: аномалии в тоне, выборе слов
  Верни `true` если текст сгенерирован AI, `false` если написан человеком.
- `tags`: Массив из 1-3 самых релевантных тегов, выбранных СТРОГО из этого списка: [{tags_str}].

Важные правила:
- Если ни один тег из списка не подходит к статье, НЕ включай эту статью в итоговый результат.
- Твой ответ должен быть ТОЛЬКО JSON-объектом обработанной статьи. Без лишних слов и комментариев.

Исходная статья для анализа:
Заголовок: {news_item['title']}
Текст: {news_item['full_text']}
"""
    
    logger.info(f"Отправка в LLM новости: {news_item['title'][:50]}...")
    llm_response_str = generate_response_sync(prompt)
    
    # Логируем ответ LLM для отладки
    logger.info(f"Ответ от LLM (первые 200 символов): {llm_response_str[:200]}")
    
    if not llm_response_str or not llm_response_str.strip():
        logger.error("LLM вернула пустой ответ")
        return None
    
    # Очищаем ответ от markdown разметки
    cleaned_response = llm_response_str.strip()
    if cleaned_response.startswith('```json'):
        cleaned_response = cleaned_response[7:]  # Убираем ```json
    if cleaned_response.startswith('```'):
        cleaned_response = cleaned_response[3:]   # Убираем ```
    if cleaned_response.endswith('```'):
        cleaned_response = cleaned_response[:-3] # Убираем ``` в конце
    
    cleaned_response = cleaned_response.strip()
    
    try:
        processed_news = json.loads(cleaned_response)
        ai_status = "AI-генерированный" if processed_news.get('is_ai_generated', False) else "Человеческий"
        logger.info(f"LLM успешно обработала новость: {processed_news.get('title', 'без заголовка')} [{ai_status}]")
        return processed_news
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON ответа от LLM: {e}")
        logger.error(f"Очищенный ответ LLM: {cleaned_response}")
        return None

def save_news_to_db(processed_news: Dict[str, Any], db_session):
    """
    Сохраняет обработанную новость в базу данных.
    """
    try:
        # Преобразуем теги из списка в строку
        tags_str = ", ".join(processed_news.get("tags", [])) if isinstance(processed_news.get("tags"), list) else processed_news.get("tags", "")
        
        news_article = NewsArticle(
            title=processed_news["title"],
            full_text=processed_news["full_text"],
            summary=processed_news["summary"],
            is_positive=processed_news["is_positive"],
            is_ai_generated=processed_news.get("is_ai_generated", False),
            tags=tags_str
        )
        
        db_session.add(news_article)
        db_session.commit()
        logger.info(f"Новость сохранена в БД: {processed_news['title'][:50]}...")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении новости в БД: {e}")
        db_session.rollback()
        return False

def run_all_parsers_and_process():
    """
    Выполняет все парсеры, проверяет дубликаты, обрабатывает новости через LLM и сохраняет в БД.
    """
    logger.info("Запуск парсинга и обработки новостей...")
    
    # Получаем сессию БД
    db = SessionLocal()
    
    try:
        # 1. Сбор данных из всех парсеров и проверка дубликатов
        unique_news = []
        total_parsed = 0
        total_skipped = 0
        
        for name, parser_func in PARSERS_REGISTRY.items():
            try:
                logger.info(f"Запуск парсера: {name}")
                news_items = parser_func()
                if news_items:
                    logger.info(f"Парсер {name} вернул {len(news_items)} новостей")
                    
                    # Проверяем каждую новость на дубликаты
                    for item in news_items:
                        total_parsed += 1
                        title = item.get("title", "")
                        full_text = item.get("full_text", "")
                        
                        logger.info(f"Проверка дубликата для: '{title[:50]}...'")
                        
                        # Проверяем, есть ли дубликат в БД
                        if check_duplicate_in_raw_news(title, full_text, db):
                            logger.info(f"Скипаем дубликат: '{title[:50]}...'")
                            total_skipped += 1
                            continue
                        
                        # Если не дубликат, сохраняем сырую новость в БД
                        if save_raw_news_to_db(title, full_text, name, db):
                            # Добавляем в список для дальнейшей обработки
                            unique_news.append({
                                "title": title,
                                "full_text": full_text,
                                "source": name
                            })
                            logger.info(f"Добавлена уникальная новость: '{title[:50]}...'")
                        
            except Exception as e:
                logger.error(f"Ошибка парсера '{name}': {e}", exc_info=True)

        logger.info(f"Статистика: всего получено {total_parsed}, уникальных {len(unique_news)}, скипнуто дубликатов {total_skipped}")
        
        if not unique_news:
            logger.warning("Нет уникальных новостей для обработки. Процесс завершен.")
            return

        # 2. Сохраняем уникальные новости в файл для справки
        raw_news_file = 'raw_news.json'
        try:
            # Очищаем файл перед записью
            if os.path.exists(raw_news_file):
                os.remove(raw_news_file)
                logger.info(f"Предыдущий файл {raw_news_file} очищен")
            
            with open(raw_news_file, 'w', encoding='utf-8') as f:
                json.dump(unique_news, f, ensure_ascii=False, indent=4)
            logger.info(f"Уникальные новости сохранены в {raw_news_file}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении новостей в файл: {e}", exc_info=True)

        # 3. Дополнительная дедупликация с помощью векторизации (опционально)
        logger.info("Начинаем дополнительную дедупликацию с помощью ML...")
        try:
            # Форматируем для функции дедупликации
            formatted_for_dedup = [{"title": item["title"], "full_text": item["full_text"]} for item in unique_news]
            deduplicated_news = deduplicate_news_with_annoy(formatted_for_dedup, threshold=0.7)
            logger.info(f"После ML дедупликации осталось {len(deduplicated_news)} новостей")
            
            # Сохраняем очищенные новости
            deduplicated_file = 'deduplicated_news.json'
            with open(deduplicated_file, 'w', encoding='utf-8') as f:
                json.dump(deduplicated_news, f, ensure_ascii=False, indent=4)
            logger.info(f"Окончательно очищенные новости сохранены в {deduplicated_file}")
            
        except Exception as e:
            logger.error(f"Ошибка при ML дедупликации: {e}", exc_info=True)
            # Если дедупликация не удалась, продолжаем с уникальными новостями
            deduplicated_news = [{"title": item["title"], "full_text": item["full_text"]} for item in unique_news]
            logger.warning("Продолжаем обработку без ML дедупликации")
            
        # 4. Обработка каждой новости отдельно через LLM и сохранение в БД
        processed_count = 0
        total_news = len(deduplicated_news)
        
        for i, news_item in enumerate(deduplicated_news):
            logger.info(f"[{i+1}/{total_news}] Обрабатываем новость...")
            
            processed_news = process_single_news_with_llm(news_item)
            
            if processed_news:
                # Сохраняем в БД
                if save_news_to_db(processed_news, db):
                    processed_count += 1
            else:
                logger.warning(f"Новость {i+1} не была обработана LLM или не подходит по тегам")
        
        logger.info(f"Обработка завершена. Успешно обработано и сохранено {processed_count} из {total_news} новостей")
        
    finally:
        db.close()

@parsers_router.post("/run", response_model=Dict[str, str], status_code=202)
async def run_all_parsers(background_tasks: BackgroundTasks):
    """
    Запускает ВСЕ парсеры, удаляет дубликаты, обрабатывает новости через LLM и сохраняет в БД.
    """
    background_tasks.add_task(run_all_parsers_and_process)
    return {"message": "Процесс парсинга, дедупликации и обработки новостей запущен в фоновом режиме."}

@parsers_router.get("/news", response_model=List[Dict[str, Any]])
async def get_processed_news(skip: int = 0, limit: int = 100):
    """
    Получает обработанные новости из базы данных.
    """
    db = SessionLocal()
    try:
        news_articles = db.query(NewsArticle).offset(skip).limit(limit).all()
        
        result = []
        for article in news_articles:
            result.append({
                "id": article.id,
                "title": article.title,
                "full_text": article.full_text,
                "summary": article.summary,
                "is_positive": article.is_positive,
                "is_ai_generated": article.is_ai_generated,
                "tags": article.tags,
                "created_at": article.created_at
            })
        
        return result
    finally:
        db.close()

@parsers_router.get("/news/{news_id}", response_model=Dict[str, Any])
async def get_news_by_id(news_id: int):
    """
    Получает конкретную новость по ID.
    """
    db = SessionLocal()
    try:
        article = db.query(NewsArticle).filter(NewsArticle.id == news_id).first()
        
        if not article:
            raise HTTPException(status_code=404, detail=f"Новость с ID {news_id} не найдена")
        
        return {
            "id": article.id,
            "title": article.title,
            "full_text": article.full_text,
            "summary": article.summary,
            "is_positive": article.is_positive,
            "is_ai_generated": article.is_ai_generated,
            "tags": article.tags,
            "created_at": article.created_at
        }
    finally:
        db.close()

@parsers_router.get("/raw-news", response_model=List[Dict[str, Any]])
async def get_raw_news(skip: int = 0, limit: int = 100):
    """
    Получает сырые новости из базы данных.
    """
    db = SessionLocal()
    try:
        raw_news = db.query(RawNews).offset(skip).limit(limit).all()
        
        result = []
        for news in raw_news:
            result.append({
                "id": news.id,
                "title": news.title,
                "full_text": news.full_text,
                "source": news.source,
                "created_at": news.created_at
            })
        
        return result
    finally:
        db.close()

@parsers_router.get("/raw-news/{news_id}", response_model=Dict[str, Any])
async def get_raw_news_by_id(news_id: int):
    """
    Получает конкретную сырую новость по ID.
    """
    db = SessionLocal()
    try:
        raw_news = db.query(RawNews).filter(RawNews.id == news_id).first()
        
        if not raw_news:
            raise HTTPException(status_code=404, detail=f"Сырая новость с ID {news_id} не найдена")
        
        return {
            "id": raw_news.id,
            "title": raw_news.title,
            "full_text": raw_news.full_text,
            "source": raw_news.source,
            "created_at": raw_news.created_at
        }
    finally:
        db.close() 