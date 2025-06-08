from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import requests
import time
import logging

from app.db.session import SessionLocal
from app.models.tradingview import TradingViewCompany
from app.api.routes.llm import generate_response_sync
from app.utils.parserCompany import parse_tradingview_stocks, get_company_image
from app.core.constants import TAG_MAP

# Создаем роутер
tradingview_router = APIRouter()
logger = logging.getLogger(__name__)

# Список допустимых тегов для компаний (берем из констант)
ALLOWED_TAGS = list(TAG_MAP.values())

# Зависимость для получения сессии БД


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_and_save_stocks_task(db: Session):
    """
    Фоновая задача для парсинга, очистки названий, обогащения данных через LLM и сохранения в БД.
    """
    companies_data = parse_tradingview_stocks()
    if not companies_data:
        logger.error("Не удалось получить данные о компаниях с TradingView")
        return

    logger.info(f"Получено {len(companies_data)} компаний с TradingView")

    for i, company in enumerate(companies_data):
        logger.info(
            f"[{i+1}/{len(companies_data)}] Обрабатываем: {company['ticker']} - {company['company_name']}")

        # --- Двухэтапная очистка названия компании ---

        # 1. Шаг 1: Грубая очистка названия
        clean_name_prompt_1 = f"""
        Извлеки чистое, общеупотребительное название компании из следующей строки: '{company['company_name']}'.
        Убери все юридические формы (ПАО, АО, и т.д.), типы акций (обыкн.), кавычки и лишние символы. 
        Верни ТОЛЬКО название. 
        
        Примеры:
        - Из "Абрау-Дюрсо ПАО - обыкн." должно получиться Абрау-Дюрсо.
        - Из "Аэрофлот-росс.авиалин(ПАО)ао" должно получиться Аэрофлот.
        - Из "Группа Позитив (ПАО)" должно получиться Группа Позитив.
        """
        step1_name = generate_response_sync(clean_name_prompt_1)

        # 2. Шаг 2: Валидация и финальная очистка
        if not step1_name or not step1_name.strip():
            logger.warning(
                f"  Шаг 1 очистки не дал результата для '{company['company_name']}'. Используем оригинал.")
            cleaned_name = company['company_name']
        else:
            logger.info(f"  Результат шага 1: '{step1_name.strip()}'")

            clean_name_prompt_2 = f"""
            Из следующего текста извлеки ТОЛЬКО название компании. Убери АБСОЛЮТНО все кавычки, пояснения и любой другой текст.
            Если на входе '"Аэрофлот"', на выходе должно быть Аэрофлот.
            Если на входе 'Название компании: "АПРИ"', на выходе должно быть АПРИ.

            Текст для обработки:
            '{step1_name}'
            """
            step2_name = generate_response_sync(clean_name_prompt_2)

            if not step2_name or not step2_name.strip():
                logger.warning(
                    f"  Шаг 2 очистки не дал результата. Используем результат шага 1, очищенный от кавычек.")
                cleaned_name = step1_name.strip().replace('"', '').replace("'", "")
            else:
                # Дополнительно чистим кавычки на случай, если LLM их все-таки добавит
                cleaned_name = step2_name.strip().replace('"', '').replace("'", "")
                logger.info(
                    f"  Название окончательно очищено: '{cleaned_name}'")

        # 3. Проверка существования компании и обновление/создание
        existing_company = db.query(TradingViewCompany).filter(
            TradingViewCompany.ticker == company["ticker"]
        ).first()

        if existing_company:
            if existing_company.description and existing_company.tags:
                logger.info(
                    f"  Компания {company['ticker']} уже полностью обработана, пропускаем.")
                continue
            db_company = existing_company
        else:
            db_company = TradingViewCompany(
                ticker=company["ticker"], link=company["link"])

        # Обновляем/устанавливаем очищенное имя
        db_company.company_name = cleaned_name

        # 4. Получение изображения
        if not db_company.image_url:
            logger.info(f"  Получаем изображение...")
            image_url = get_company_image(company["link"])
            db_company.image_url = image_url
            logger.info(
                f"  Изображение {'найдено' if image_url else 'не найдено'}.")

        # 5. Генерация описания
        if not db_company.description:
            logger.info("  Генерируем описание...")
            description_prompt = f"Напиши краткое деловое описание компании {db_company.company_name} (тикер: {db_company.ticker}). Описание должно включать основную сферу деятельности компании, её позицию на рынке, ключевые направления бизнеса. Ответ должен быть на русском языке, 3-5 предложений."
            description = generate_response_sync(description_prompt)
            db_company.description = description.strip() if description else None
            logger.info(
                f"  Описание {'сгенерировано' if description else 'не сгенерировано'}.")

        # 6. Двухэтапная генерация тегов
        if not db_company.tags:
            allowed_tags_str = ", ".join(ALLOWED_TAGS)

            # Шаг 1: Основной промпт для генерации
            logger.info("  Генерируем теги (шаг 1/2)...")
            tags_prompt_1 = f"Определи от 3 до 5 ключевых тегов для компании {db_company.company_name} (тикер: {db_company.ticker}), выбрав их СТРОГО из следующего списка: [{allowed_tags_str}]. Не придумывай новые теги. Формат ответа: тег1, тег2, тег3."
            step1_tags = generate_response_sync(tags_prompt_1)

            # Шаг 2: Валидация и финальная очистка
            if not step1_tags or not step1_tags.strip():
                logger.warning(
                    f"  Шаг 1 генерации тегов не дал результата для {db_company.company_name}.")
                db_company.tags = None
            else:
                logger.info(f"  Результат шага 1: '{step1_tags.strip()}'")
                logger.info("  Генерируем теги (шаг 2/2)...")

                tags_prompt_2 = f"""
                Из следующего текста извлеки ТОЛЬКО те теги, которые есть в этом списке: [{allowed_tags_str}].
                Убери все пояснения, примечания, заголовки, звездочки и любой другой текст.
                Верни только теги, разделенные запятой.

                Текст для обработки:
                '{step1_tags}'
                """
                step2_tags = generate_response_sync(tags_prompt_2)

                if not step2_tags or not step2_tags.strip():
                    logger.warning(
                        "  Шаг 2 генерации тегов не дал результата. Пытаемся извлечь валидные теги из ответа шага 1...")
                    # Запасной вариант: ищем валидные теги в тексте ответа шага 1
                    found_tags = [
                        tag for tag in ALLOWED_TAGS if tag in step1_tags]
                    final_tags = ", ".join(found_tags)
                else:
                    final_tags = step2_tags.strip().removesuffix(
                        ',')  # Убираем возможную запятую в конце

                db_company.tags = final_tags if final_tags else None

            logger.info(f"  Итоговые теги: '{db_company.tags}'")

        # 7. Сохранение в БД
        if not existing_company:
            db.add(db_company)
        db.commit()

        logger.info(
            f"  Компания {db_company.ticker} успешно обработана и сохранена.")
        time.sleep(1)

    logger.info("Обработка всех компаний завершена.")


@tradingview_router.post("/parse", response_model=Dict[str, Any], status_code=202)
async def parse_and_save_stocks(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Запускает парсинг акций с TradingView, генерирует описания и теги через LLM
    и сохраняет результаты в базу данных.
    """
    background_tasks.add_task(parse_and_save_stocks_task, db)
    return {"status": "success", "message": "Парсинг и обработка данных запущены в фоновом режиме"}


@tradingview_router.get("/companies", response_model=List[Dict[str, Any]])
async def get_companies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Получает список компаний из базы данных с пагинацией.
    """
    companies = db.query(TradingViewCompany).offset(skip).limit(limit).all()

    result = []
    for company in companies:
        result.append({
            "id": company.id,
            "ticker": company.ticker,
            "company_name": company.company_name,
            "link": company.link,
            "image_url": company.image_url,
            "description": company.description,
            "tags": company.tags,
            "created_at": company.created_at
        })

    return result


@tradingview_router.get("/companies/{ticker}", response_model=Dict[str, Any])
async def get_company_by_ticker(ticker: str, db: Session = Depends(get_db)):
    """
    Получает информацию о компании по её тикеру.
    """
    company = db.query(TradingViewCompany).filter(
        TradingViewCompany.ticker == ticker).first()

    if not company:
        raise HTTPException(
            status_code=404, detail=f"Компания с тикером {ticker} не найдена")

    return {
        "id": company.id,
        "ticker": company.ticker,
        "company_name": company.company_name,
        "link": company.link,
        "image_url": company.image_url,
        "description": company.description,
        "tags": company.tags,
        "created_at": company.created_at
    }
