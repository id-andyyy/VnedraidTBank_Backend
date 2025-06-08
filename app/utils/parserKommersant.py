import requests
from bs4 import BeautifulSoup
import logging
import time
import json
import re

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
    Основная функция для парсинга новостей с Коммерсанта с использованием requests и BeautifulSoup.
    - Заходит на главную страницу новостей.
    - Собирает ссылки на первые 10 новостей.
    - Переходит по каждой ссылке и извлекает полный текст.
    - Возвращает список новостей с заголовками и полным текстом.
    """
    URL = "https://www.kommersant.ru/finance?from=main"
    news_data = []

    try:
        logger.info(f"Загрузка главной страницы: {URL}")
        response = requests.get(URL, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Собираем ссылки на новости из ленты
        news_articles = soup.find_all('article', class_='uho rubric_lenta__item js-article')
        logger.info(f"Найдено {len(news_articles)} статей на главной странице.")

        if not news_articles:
            logger.warning("Новостная лента пуста. Возможно, контент загружается динамически (через JS).")
            return []

        # Ограничиваемся первыми 10 новостями
        for i, article in enumerate(news_articles[:10]):
            try:
                # Извлекаем URL статьи из data-атрибута
                article_url = article.get('data-article-url')
                if not article_url:
                    # Пробуем найти ссылку в заголовке
                    title_link = article.find('a', class_='uho__link uho__link--overlay')
                    if title_link and title_link.get('href'):
                        article_url = f"https://www.kommersant.ru{title_link.get('href')}"
                    else:
                        logger.warning(f"Не найден URL для статьи {i+1}")
                        continue

                logger.info(f"[{i+1}/10] Парсинг статьи: {article_url}")

                # Получаем полный текст статьи
                article_response = requests.get(article_url, headers=HEADERS, timeout=10)
                article_response.raise_for_status()
                article_soup = BeautifulSoup(article_response.content, 'html.parser')

                # Извлекаем заголовок
                title_tag = article_soup.find('h1', class_='doc_header__name')
                title = title_tag.get_text(strip=True) if title_tag else "Заголовок не найден"

                # Извлекаем основной текст статьи из div с классом doc__body
                content_elem = article_soup.find('div', class_='doc__body')
                full_text = ""
                
                if content_elem:
                    # Извлекаем все параграфы с текстом
                    text_paragraphs = content_elem.find_all('p', class_='doc__text')
                    content_parts = []
                    for p in text_paragraphs:
                        # Убираем HTML теги и извлекаем чистый текст
                        text = p.get_text(strip=True)
                        if text:
                            content_parts.append(text)
                    full_text = "\n".join(content_parts)
                else:
                    full_text = "Текст статьи не найден"

                # Проверяем, что мы получили валидные данные
                if "Заголовок не найден" not in title and "Текст статьи не найден" not in full_text and full_text.strip():
                    news_data.append({
                        'title': title,
                        'full_text': full_text
                    })
                    logger.info(f"Успешно спарсена статья: {title[:50]}...")
                else:
                    logger.warning(f"Пропускаем статью {i+1} - недостаточно данных")

            except requests.RequestException as e:
                logger.error(f"Ошибка при загрузке статьи {i+1}: {e}")
            except Exception as e:
                logger.error(f"Неожиданная ошибка при обработке статьи {i+1}: {e}")
            
            # Небольшая задержка между запросами
            time.sleep(0.5)

    except requests.RequestException as e:
        logger.error(f"Не удалось загрузить главную страницу: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")

    return news_data


def main():
    """Основная функция для запуска парсера"""
    logger.info("Запуск парсера Коммерсант (requests + bs4)...")
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
            with open('kommersantNews.json', 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            logger.info("Данные успешно сохранены в файл kommersantNews.json")
        except IOError as e:
            logger.error(f"Ошибка при записи в файл kommersantNews.json: {e}")
        
        # Показываем превью первых новостей
        print("\n🗞️  Превью спарсенных новостей:")
        print("=" * 80)
        for i, news in enumerate(output_data[:3], 1):
            print(f"\n{i}. {news['Name']}")
            print(f"   📝 {news['Description'][:100]}...")
            print("-" * 80)
        
    else:
        logger.warning("Не удалось спарсить ни одной новости. Возможно, требуется проверка селекторов.")


if __name__ == "__main__":
    main() 