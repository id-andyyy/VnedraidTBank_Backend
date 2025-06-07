from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import requests
import time

from app.db.session import SessionLocal
from app.models.tradingview import TradingViewCompany
from app.api.routes.llm import generate_response_sync
from app.utils.parserCompany import parse_tradingview_stocks, get_company_image

# Создаем роутер
tradingview_router = APIRouter()

# Список допустимых тегов для компаний
ALLOWED_TAGS = [
    "энергетика",           # Нефть, газ, электроэнергетика, возобновляемые источники
    "финансы",             # Банки, страховые компании, инвестиционные фонды, лизинг
    "технологии",          # IT, софт, хард, телеком, искусственный интеллект
    "промышленность",      # Металлургия, химия, машиностроение, оборонка
    "потребительский сектор", # Ритейл, фарма, товары повседневного спроса, медиа
    "инфраструктура",      # Транспорт, строительство, ЖКХ, логистика
    "сельское хозяйство",  # Растениеводство, животноводство, агротехнологии
    "здравоохранение",     # Медицинские услуги, оборудование, биотехнологии
    "недвижимость",        # Девелопмент, управление недвижимостью, REIT
    "материалы",           # Строительные материалы, композиты, сырье
    "телекоммуникации",    # Операторы связи, интернет-провайдеры
    "развлечения",         # Игры, кино, спорт, туризм
    "образование",         # EdTech, онлайн-обучение, образовательные услуги
    "электронная коммерция" # Онлайн-торговля, маркетплейсы, платежные системы
]

# Зависимость для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@tradingview_router.post("/parse", response_model=Dict[str, Any])
async def parse_and_save_stocks(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Запускает парсинг акций с TradingView, генерирует описания и теги через LLM
    и сохраняет результаты в базу данных.
    """
    # Запускаем парсинг как фоновую задачу
    background_tasks.add_task(parse_and_save_stocks_task, db)
    
    return {"status": "success", "message": "Парсинг и обработка данных запущены в фоновом режиме"}

def parse_and_save_stocks_task(db: Session):
    """
    Фоновая задача для парсинга, обогащения данных через LLM и сохранения в БД.
    """
    # Получаем данные о компаниях с сайта TradingView
    companies_data = parse_tradingview_stocks()
    
    if not companies_data:
        print("Не удалось получить данные о компаниях")
        return
    
    print(f"Получено {len(companies_data)} компаний с TradingView")
    
    # Обрабатываем каждую компанию
    for i, company in enumerate(companies_data):
        # Проверяем, существует ли компания с таким тикером
        existing_company = db.query(TradingViewCompany).filter(
            TradingViewCompany.ticker == company["ticker"]
        ).first()
        
        if existing_company:
            # Если компания уже существует с описанием и тегами, пропускаем
            if existing_company.description and existing_company.tags:
                print(f"Компания {company['ticker']} уже имеет описание и теги")
                # Проверяем, есть ли изображение
                if not existing_company.image_url:
                    print(f"Получаем изображение для {company['ticker']}...")
                    image_url = get_company_image(company["link"])
                    if image_url:
                        existing_company.image_url = image_url
                        print(f"  Добавлено изображение: {image_url[:100]}...")
                        db.commit()
                    else:
                        print(f"  Изображение не найдено")
                else:
                    print(f"Компания {company['ticker']} уже имеет изображение, пропускаем")
                continue
            else:
                db_company = existing_company
        else:
            # Создаем новую запись
            db_company = TradingViewCompany(
                ticker=company["ticker"],
                company_name=company["company_name"],
                link=company["link"]
            )
        
        print(f"[{i+1}/{len(companies_data)}] Обрабатываем {company['ticker']} - {company['company_name']}")
        
        # Получаем изображение компании
        if not db_company.image_url:
            print(f"  Получаем изображение...")
            image_url = get_company_image(company["link"])
            if image_url:
                db_company.image_url = image_url
                print(f"  Добавлено изображение: {image_url[:100]}...")
            else:
                print(f"  Изображение не найдено")
        
        # Генерируем описание компании через LLM
        if not db_company.description:
            description_prompt = f"""
            Напиши краткое деловое описание компании {company['company_name']} (тикер: {company['ticker']}).
            Описание должно включать основную сферу деятельности компании, её позицию на рынке,
            ключевые направления бизнеса. Ответ должен быть на русском языке, 3-5 предложений.
            """
            
            description = generate_response_sync(description_prompt)
            if description:
                db_company.description = description.strip()
                print(f"  Сгенерировано описание: {description[:100]}...")
        
        # Генерируем теги для компании через LLM
        if not db_company.tags:
            allowed_tags_str = ", ".join(ALLOWED_TAGS)
            tags_prompt = f"""
            Определи от 3 до 5 ключевых тегов для компании {company['company_name']} (тикер: {company['ticker']}), выбрав их СТРОГО из следующего списка:
            [{allowed_tags_str}]

            Теги должны максимально точно отражать отрасль и сферу деятельности компании.
            Не придумывай новые теги. Используй только те, что есть в предоставленном списке.
            
            Формат ответа: тег1, тег2, тег3 (без нумерации, просто через запятую).
            """
            
            tags = generate_response_sync(tags_prompt)
            if tags:
                db_company.tags = tags.strip()
                print(f"  Сгенерированы теги: {tags}")
        
        # Добавляем в БД
        if not existing_company:
            db.add(db_company)
        
        # Сохраняем изменения для каждой компании
        db.commit()
        
        # Добавляем задержку между запросами к LLM для избежания перегрузки
        time.sleep(1)
    
    print(f"Обработка завершена. Всего обработано {len(companies_data)} компаний")

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
    company = db.query(TradingViewCompany).filter(TradingViewCompany.ticker == ticker).first()
    
    if not company:
        raise HTTPException(status_code=404, detail=f"Компания с тикером {ticker} не найдена")
    
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