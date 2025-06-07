import requests
from bs4 import BeautifulSoup
import logging
import time
import json

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
}

def get_news_data():
    """
    Основная функция для парсинга новостей с РБК с использованием requests и BeautifulSoup.
    - Заходит на главную страницу.
    - Собирает ссылки на новости.
    - Переходит по каждой ссылке и извлекает полный текст.
    - Возвращает список новостей с заголовками и полным текстом.
    """
    URL = "https://www.rbc.ru/quote?utm_source=topline"
    news_data = []

    try:
        logger.info(f"Загрузка главной страницы: {URL}")
        response = requests.get(URL, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Собираем ссылки на новости
        news_links = soup.select("a.news-feed__item")
        logger.info(f"Найдено {len(news_links)} ссылок на новости.")

        if not news_links:
            logger.warning("Новостная лента пуста. Возможно, контент загружается динамически (через JS).")
            return []

        # Ограничимся 10 новостями для примера
        for i, link_tag in enumerate(news_links[:10]):
            href = link_tag.get('href')
            if not href:
                continue

            url = href if href.startswith('http') else f"https://www.rbc.ru{href}"
            logger.info(f"[{i+1}/{len(news_links[:10])}] Парсинг статьи: {url}")

            try:
                article_response = requests.get(url, headers=HEADERS, timeout=10)
                article_response.raise_for_status()
                article_soup = BeautifulSoup(article_response.content, 'html.parser')

                # Извлекаем заголовок
                title_tag = article_soup.find('h1')
                title = title_tag.get_text(strip=True) if title_tag else "Заголовок не найден"

                # Извлекаем основной текст статьи
                article_body = article_soup.select_one(".article__text, .article_text")
                if article_body:
                    paragraphs = [p.get_text(strip=True) for p in article_body.find_all('p')]
                    full_text = "\n".join(paragraphs)
                else:
                    full_text = "Текст статьи не найден"
                
                if "Заголовок не найден" not in title and "Текст статьи не найден" not in full_text:
                    news_data.append({
                        'title': title,
                        'full_text': full_text
                    })

            except requests.RequestException as e:
                logger.error(f"Ошибка при загрузке статьи {url}: {e}")
            
            time.sleep(0.5) # Небольшая задержка

    except requests.RequestException as e:
        logger.error(f"Не удалось загрузить главную страницу: {e}")

    return news_data


def main():
    """Основная функция для запуска парсера"""
    logger.info("Запуск парсера РБК (requests + bs4)...")
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
            with open('allNews.json', 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            logger.info("Данные успешно сохранены в файл allNews.json")
        except IOError as e:
            logger.error(f"Ошибка при записи в файл allNews.json: {e}")
        
    else:
        logger.warning("Не удалось спарсить ни одной новости. Вероятно, требуется JS-рендеринг.")


if __name__ == "__main__":
    main() 