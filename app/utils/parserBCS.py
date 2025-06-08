import asyncio
import logging
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_article_content_from_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Извлекает содержимое статьи из локального HTML-файла.

    Args:
        file_path: Путь к HTML-файлу.

    Returns:
        Словарь с заголовком и текстом статьи или None в случае ошибки.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        soup = BeautifulSoup(content, "html.parser")
        
        # Извлечение заголовка
        title_tag = soup.find("h1", class_="rp1F")
        title = title_tag.find(text=True, recursive=False).strip() if title_tag else "Заголовок не найден"

        # Извлечение основного контента статьи
        full_text = ""
        content_div = soup.find("div", {"data-id": "publication-content"})
        if content_div:
            paragraphs = content_div.find_all("p")
            full_text = "\n".join(p.get_text(strip=True) for p in paragraphs)

        if not title or not full_text:
            logger.warning(f"Не удалось полностью извлечь данные из файла: {file_path}")
            return None

        return {"title": title, "full_text": full_text}

    except FileNotFoundError:
        logger.error(f"Файл не найден: {file_path}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при обработке файла {file_path}: {e}")

    return None


async def parse_bcs_express() -> List[Dict[str, Any]]:
    """
    Парсит локальный HTML-файл для получения данных о новости.
    Это заглушка, пока не будет реализован полноценный парсер.

    Returns:
        Список с одной новостью или пустой список.
    """
    logger.info("Запуск парсера-заглушки для BCS Express из локального файла.")
    article = get_article_content_from_file('testPage.html')
    if article:
        logger.info("Статья из файла testPage.html успешно обработана.")
        return [article]
    
    logger.warning("Не удалось обработать статью из testPage.html.")
    return []


async def main():
    """Основная функция для запуска парсера."""
    news = await parse_bcs_express()
    if news:
        for i, article in enumerate(news, 1):
            print(f"--- Новость {i} (из файла testPage.html) ---")
            print(f"Заголовок: {article['title']}")
            print(f"Текст: {article['full_text'][:300]}...")
            print("-" * 20)
    else:
        print("Не удалось получить новости из файла.")

if __name__ == "__main__":
    asyncio.run(main()) 