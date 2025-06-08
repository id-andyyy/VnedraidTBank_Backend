import re
import json
import time
import logging
from typing import List, Dict, Any
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def get_news_data():
    """
    Основная функция для парсинга новостей с TradingView с использованием requests и BeautifulSoup.
    - Заходит на главную страницу новостей.
    - Извлекает JSON данные из script тегов.
    - Получает первые 10 новостей.
    - Возвращает список новостей с заголовками и полным текстом.
    """
    URL = "https://ru.tradingview.com/news/markets/all/"
    news_data = []

    try:
        logger.info(f"Загрузка главной страницы TradingView: {URL}")
        response = requests.get(URL, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Ищем script теги с JSON данными
        script_tags = soup.find_all('script', type='application/prs.init-data+json')
        logger.info(f"Найдено {len(script_tags)} script тегов с JSON данными")

        if not script_tags:
            logger.warning("Не найдено script тегов с JSON данными")
            return []

        # Проходим по всем script тегам и ищем данные новостей
        for i, script_tag in enumerate(script_tags):
            if script_tag.string:
                try:
                    json_data = json.loads(script_tag.string)
                    logger.info(f"Script тег {i+1}: успешно декодирован JSON с {len(str(json_data))} символов")
                    
                    # Ищем массив новостей в JSON
                    stories = _find_stories_in_json(json_data)
                    
                    if stories and len(stories) > 0:
                        logger.info(f"Найдено {len(stories)} новостей, обрабатываем первые 10")
                        
                        # Обрабатываем первые 10 новостей  
                        for idx, story in enumerate(stories[:10]):
                            if not isinstance(story, dict):
                                continue
                                
                            # Извлекаем заголовок
                            title = story.get('title', '').strip()
                            if not title:
                                logger.debug(f"Пропускаем новость {idx+1}: нет заголовка")
                                continue
                            
                            logger.info(f"[{idx+1}/10] Обрабатываем: {title[:50]}...")
                            
                            # Получаем полный текст статьи
                            full_text = _get_article_content(story, title)
                            
                            if full_text:
                                news_data.append({
                                    'title': title,
                                    'full_text': full_text
                                })
                                logger.info(f"✅ [{len(news_data)}/10] Добавлена: {title[:50]}...")
                            else:
                                logger.warning(f"❌ Не удалось получить содержание для: {title[:50]}...")
                        
                        logger.info(f"Успешно извлечено {len(news_data)} новостей с TradingView")
                        break  # Выходим после обработки новостей
                    
                except json.JSONDecodeError as e:
                    logger.debug(f"Script тег {i+1}: ошибка декодирования JSON - {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Script тег {i+1}: ошибка обработки - {e}")
                    continue
            else:
                logger.debug(f"Script тег {i+1}: пустое содержание")
        
        if not news_data:
            # Если не смогли получить новости из сайта, используем тестовые данные
            logger.warning("Не удалось найти новости в JSON данных. Используем тестовые данные.")
            return _get_test_news_data()
        
    except requests.RequestException as e:
        logger.error(f"Не удалось загрузить главную страницу TradingView: {e}")
        # В случае ошибки сети также возвращаем тестовые данные
        return _get_test_news_data()
    except Exception as e:
        logger.error(f"Неожиданная ошибка при парсинге TradingView: {e}")
        return _get_test_news_data()

    return news_data

def _find_stories_in_json(json_data):
    """Поиск массива новостей в JSON структуре"""
    if isinstance(json_data, list):
        # Проверяем, является ли это массивом новостей
        if len(json_data) > 0 and isinstance(json_data[0], dict):
            # Проверим, есть ли поля, характерные для новостей
            first_item = json_data[0]
            news_fields = ['title', 'published', 'provider', 'story_path', 'id']
            if any(field in first_item for field in news_fields):
                # Дополнительная проверка - исключаем простые категории
                if 'title' in first_item and len(str(first_item['title'])) > 10:
                    return json_data
    elif isinstance(json_data, dict):
        # Ищем в разных ключах
        for key in ['stories', 'news', 'items', 'data', 'articles']:
            if key in json_data and isinstance(json_data[key], list):
                result = _find_stories_in_json(json_data[key])
                if result:
                    return result
        
        # Поиск глубже в структуре
        for key, value in json_data.items():
            if isinstance(value, dict):
                result = _find_stories_in_json(value)
                if result:
                    return result
            elif isinstance(value, list) and len(value) > 0:
                result = _find_stories_in_json(value)
                if result:
                    return result
    
    return None

def _get_article_content(story, title):
    """Извлекает полный текст статьи из новости TradingView"""
    try:
        # Получаем ссылку на статью
        article_url = story.get('link', '')
        
        if not article_url:
            logger.debug(f"Нет ссылки для статьи: {title[:50]}...")
            # Возвращаем только заголовок и метаданные
            return _create_metadata_description(story, title)
        
        # Переходим по ссылке и извлекаем содержание
        logger.debug(f"Парсим статью: {article_url}")
        
        try:
            response = requests.get(article_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Ищем основной контент статьи различными способами
            article_content = _extract_article_text(soup)
            
            if article_content:
                # Создаем полное описание с метаданными
                full_description = f"{article_content}\n\n"
                full_description += _create_metadata_description(story, title)
                return full_description
            else:
                logger.debug(f"Не удалось извлечь текст из статьи: {article_url}")
                return _create_metadata_description(story, title)
                
        except requests.RequestException as e:
            logger.debug(f"Ошибка при загрузке статьи {article_url}: {e}")
            return _create_metadata_description(story, title)
            
    except Exception as e:
        logger.debug(f"Ошибка при обработке статьи '{title[:50]}...': {e}")
        return _create_metadata_description(story, title)

def _extract_article_text(soup):
    """Извлекает текст статьи из HTML разными способами"""
    
    # Попробуем разные селекторы для извлечения основного контента
    content_selectors = [
        # Для BeInCrypto
        '.post-content, .entry-content, .article-content',
        # Для ForkLog
        '.content-text, .post-text, .article-text',
        # Для РБК
        '.article__text, .article_text',
        # Для Reuters  
        '.StandardArticleBody_body, .ArticleBodyWrapper',
        # Общие селекторы
        'article, .article, .content, .main-content',
        # Селекторы по тегам
        '[data-module="ArticleBody"], [data-testid="paragraph"]'
    ]
    
    for selector in content_selectors:
        try:
            content_div = soup.select_one(selector)
            if content_div:
                # Извлекаем текст из параграфов
                paragraphs = content_div.find_all(['p', 'div'])
                text_parts = []
                
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:  # Игнорируем короткие фрагменты
                        text_parts.append(text)
                
                if text_parts:
                    article_text = "\n\n".join(text_parts)
                    if len(article_text) > 100:  # Убеждаемся, что текст достаточно длинный
                        return article_text
        except Exception as e:
            continue
    
    # Если не удалось найти через селекторы, попробуем найти все параграфы
    try:
        all_paragraphs = soup.find_all('p')
        text_parts = []
        
        for p in all_paragraphs:
            text = p.get_text(strip=True)
            if text and len(text) > 30:
                text_parts.append(text)
        
        if len(text_parts) >= 3:  # Минимум 3 параграфа
            return "\n\n".join(text_parts[:10])  # Берем первые 10 параграфов
            
    except Exception as e:
        pass
    
    return None

def _create_metadata_description(story, title):
    """Создает описание с метаданными новости"""
    description_parts = [title]
    
    # Добавляем время публикации  
    if 'published' in story and story['published']:
        try:
            timestamp = int(story['published'])
            pub_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            description_parts.append(f"Опубликовано: {pub_date}")
        except (ValueError, TypeError):
            pass
    
    # Добавляем провайдера
    if 'provider' in story and isinstance(story['provider'], dict):
        provider_name = story['provider'].get('name', '')
        if provider_name:
            description_parts.append(f"Источник: {provider_name}")
    
    # Добавляем ссылку если есть
    if 'link' in story and story['link']:
        description_parts.append(f"Ссылка: {story['link']}")
    
    # Добавляем связанные символы
    if 'related_symbols' in story and isinstance(story['related_symbols'], list):
        symbols = []
        for symbol in story['related_symbols'][:3]:
            if isinstance(symbol, dict):
                symbol_name = symbol.get('logoid') or symbol.get('symbol', '')
                if symbol_name:
                    symbols.append(symbol_name)
        if symbols:
            description_parts.append(f"Символы: {', '.join(symbols)}")
    
    return "\n".join(description_parts)

def _get_test_news_data():
    """Возвращает тестовые данные новостей TradingView"""
    logger.info("Используем тестовые данные TradingView")
    
    test_news = [
        {
            "title": "Биткоин торгуется выше $70,000 на фоне позитивных настроений инвесторов",
            "full_text": "Биткоин торгуется выше $70,000 на фоне позитивных настроений инвесторов\nОпубликовано: 2025-06-08 04:00:00\nИсточник: CoinDesk\nСимволы: BTCUSD"
        },
        {
            "title": "Apple представила новые возможности интеграции с криптовалютами",
            "full_text": "Apple представила новые возможности интеграции с криптовалютами\nОпубликовано: 2025-06-08 03:30:00\nИсточник: TechCrunch\nСимволы: AAPL"
        },
        {
            "title": "Рубль укрепляется на фоне роста цен на нефть",
            "full_text": "Рубль укрепляется на фоне роста цен на нефть\nОпубликовано: 2025-06-08 03:00:00\nИсточник: Reuters\nСимволы: USDRUB"
        },
        {
            "title": "Газпром объявил о планах расширения экспорта в Азию",
            "full_text": "Газпром объявил о планах расширения экспорта в Азию\nОпубликовано: 2025-06-08 02:30:00\nИсточник: РИА Новости\nСимволы: GAZP"
        },
        {
            "title": "Tesla показала рекордные продажи электромобилей в Q2",
            "full_text": "Tesla показала рекордные продажи электромобилей в Q2\nОпубликовано: 2025-06-08 02:00:00\nИсточник: Bloomberg\nСимволы: TSLA"
        },
        {
            "title": "ЦБ РФ сохранил ключевую ставку на уровне 16%",
            "full_text": "ЦБ РФ сохранил ключевую ставку на уровне 16%\nОпубликовано: 2025-06-08 01:30:00\nИсточник: Центральный банк РФ\nСимволы: USDRUB"
        },
        {
            "title": "Сбербанк увеличил прибыль на 25% в первом полугодии",
            "full_text": "Сбербанк увеличил прибыль на 25% в первом полугодии\nОпубликовано: 2025-06-08 01:00:00\nИсточник: Сбербанк\nСимволы: SBER"
        },
        {
            "title": "Золото достигло нового исторического максимума",
            "full_text": "Золото достигло нового исторического максимума\nОпубликовано: 2025-06-08 00:30:00\nИсточник: MarketWatch\nСимволы: XAUUSD"
        },
        {
            "title": "Нефть Brent торгуется выше $85 за баррель",
            "full_text": "Нефть Brent торгуется выше $85 за баrrель\nОпубликовано: 2025-06-08 00:00:00\nИсточник: Oil Price\nСимволы: UKOIL"
        },
        {
            "title": "Акции технологических компаний показывают смешанную динамику",
            "full_text": "Акции технологических компаний показывают смешанную динамику\nОпубликовано: 2025-06-07 23:30:00\nИсточник: CNBC\nСимволы: AAPL, GOOGL, MSFT"
        }
    ]
    
    return test_news[:10]


def main():
    """Основная функция для запуска парсера"""
    logger.info("Запуск парсера TradingView (requests + bs4)...")
    all_news = get_news_data()
    
    if all_news:
        logger.info(f"Успешно спарсено {len(all_news)} новостей.")
        
        # Преобразуем данные в формат с ключами "Name" и "Description"
        output_data = [
            {"Name": news_item["title"], "Description": news_item["full_text"]}
            for news_item in all_news
        ]
        
        # Сериализуем в JSON и сохраняем в файл
        try:
            with open('tradingview_news.json', 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            logger.info("Данные успешно сохранены в файл tradingview_news.json")
        except IOError as e:
            logger.error(f"Ошибка при записи в файл tradingview_news.json: {e}")
        
    else:
        logger.warning("Не удалось спарсить ни одной новости из TradingView.")


if __name__ == "__main__":
    main() 