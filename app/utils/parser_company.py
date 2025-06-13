import os
import re
import requests
import time
from bs4 import BeautifulSoup
from random import uniform
from fake_useragent import UserAgent

def get_random_user_agent():
    """Генерирует случайный User-Agent"""
    try:
        ua = UserAgent()
        return ua.random
    except:
        # Если библиотека не работает, возвращаем стандартный User-Agent
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def fetch_tradingview_page(url="https://ru.tradingview.com/markets/stocks-russia/market-movers-all-stocks/"):
    """
    Загружает HTML-страницу с сайта TradingView.
    
    Args:
        url (str): URL-адрес страницы для загрузки
        
    Returns:
        str: HTML-контент страницы или None в случае ошибки
    """
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://ru.tradingview.com/",
        "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        # Добавляем небольшую задержку для имитации человеческого поведения
        time.sleep(uniform(1, 3))
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Проверка на ошибки HTTP
            
        return response.text
    except Exception as e:
        print(f"Ошибка при загрузке страницы: {e}")
        return None

def get_company_image(company_url):
    """
    Извлекает URL изображения компании с её страницы на TradingView.
    
    Args:
        company_url (str): URL страницы компании на TradingView
        
    Returns:
        str: URL изображения компании или None, если изображение не найдено
    """
    try:
        html_content = fetch_tradingview_page(company_url)
        if not html_content:
            return None
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Ищем изображение компании
        # TradingView обычно размещает логотип компании в мета-тегах или в специальных контейнерах
        # Попробуем несколько вариантов поиска
        
        # Вариант 1: Поиск в мета-тегах OpenGraph
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image.get('content')
            
        # Вариант 2: Поиск изображения в контейнере с информацией о компании
        image_container = soup.select_one('.tv-symbol-header__logo-container img')
        if image_container and image_container.get('src'):
            src = image_container.get('src')
            # Проверяем, если это относительный URL, делаем его абсолютным
            if src.startswith('/'):
                return f"https://ru.tradingview.com{src}"
            return src
            
        # Вариант 3: Поиск в основном контейнере с информацией о компании
        company_image = soup.select_one('.tv-circle-logo__image')
        if company_image and company_image.get('src'):
            src = company_image.get('src')
            if src.startswith('/'):
                return f"https://ru.tradingview.com{src}"
            return src
            
        return None
    except Exception as e:
        print(f"Ошибка при получении изображения компании: {e}")
        return None

def parse_tradingview_stocks(html_content=None):
    """
    Парсит информацию о российских акциях с TradingView.
    Если HTML-контент не предоставлен, загружает его с сайта.
    
    Args:
        html_content (str, optional): HTML-контент для парсинга
        
    Returns:
        list: Список словарей с информацией о компаниях
    """
    # Если HTML-контент не предоставлен, загружаем его с сайта
    if not html_content:
        print("Загрузка данных с сайта TradingView...")
        html_content = fetch_tradingview_page()
        
        if not html_content:
            print("Ошибка: Не удалось загрузить данные с сайта")
            return None
    
    # Создаем объект BeautifulSoup для парсинга HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Находим все ссылки на страницы компаний
    stocks_data = []
    
    # Паттерн для поиска тикеров и компаний
    ticker_links = soup.find_all('a', href=lambda href: href and href.startswith('/symbols/RUS-'))
    
    for link in ticker_links:
        ticker = link.text.strip()
        href = link.get('href')
        full_url = f"https://ru.tradingview.com{href}"
        
        # Находим название компании (оно обычно находится в соседнем элементе sup)
        company_name_elem = link.find_next('sup', class_='apply-common-tooltip')
        company_name = company_name_elem.get('title') if company_name_elem else "Название не найдено"
        
        # Создаем запись о компании
        company_data = {
            'ticker': ticker,
            'company_name': company_name,
            'link': full_url
        }
        
        # Добавляем в список
        stocks_data.append(company_data)
    
    return stocks_data

def main():
    """Основная функция программы"""
    print("Начинаем парсинг данных с TradingView...")
    stocks_data = parse_tradingview_stocks()
    
    if stocks_data:
        print(f"Найдено {len(stocks_data)} компаний")
        
        # Выводим первые 10 компаний для примера
        print("\nПример данных (первые 10 компаний):")
        for i, stock in enumerate(stocks_data[:10]):
            print(f"{i+1}. {stock['ticker']} - {stock['company_name']}")
            print(f"   Ссылка: {stock['link']}")
            
            # Получаем и выводим URL изображения для первых 3-х компаний
            if i < 3:
                print("   Получение изображения...")
                image_url = get_company_image(stock['link'])
                if image_url:
                    print(f"   Изображение: {image_url}")
                else:
                    print("   Изображение не найдено")
                # Добавляем небольшую задержку
                time.sleep(2)
    else:
        print("Не удалось получить данные о компаниях")

if __name__ == "__main__":
    main() 