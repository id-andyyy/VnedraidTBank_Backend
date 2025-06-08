#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер для сайта Коммерсант (kommersant.ru)
Поддерживает парсинг главной страницы и отдельных статей.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
import logging
from urllib.parse import urljoin, urlparse
import csv


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kommersant_parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """Структура данных для новости"""
    id: str
    title: str
    url: str
    datetime: str
    rubric: str
    author: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None


class KommersantParser:
    """Парсер для сайта Коммерсант"""
    
    def __init__(self, delay: float = 1.0):
        """
        Инициализация парсера
        
        Args:
            delay: Задержка между запросами в секундах
        """
        self.base_url = "https://www.kommersant.ru"
        self.session = requests.Session()
        self.delay = delay
        
        # User-Agent для имитации браузера
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        """
        Выполняет HTTP запрос и возвращает BeautifulSoup объект
        
        Args:
            url: URL для запроса
            
        Returns:
            BeautifulSoup объект или None в случае ошибки
        """
        try:
            logger.info(f"Запрос к: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Проверяем кодировку
            if response.encoding != 'utf-8':
                response.encoding = 'utf-8'
                
            soup = BeautifulSoup(response.text, 'html.parser')
            time.sleep(self.delay)  # Задержка между запросами
            return soup
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе {url}: {e}")
            return None

    def parse_main_page(self, url: str = None) -> List[NewsItem]:
        """
        Парсит главную страницу с лентой новостей
        
        Args:
            url: URL главной страницы (по умолчанию лента новостей)
            
        Returns:
            Список объектов NewsItem
        """
        if url is None:
            url = f"{self.base_url}/lenta?from=all_lenta"
            
        soup = self._make_request(url)
        if not soup:
            return []

        news_items = []
        
        # Ищем все статьи в ленте новостей
        articles = soup.find_all('article', class_='uho rubric_lenta__item js-article')
        
        for article in articles:
            try:
                news_item = self._parse_news_item_from_main(article)
                if news_item:
                    news_items.append(news_item)
            except Exception as e:
                logger.error(f"Ошибка при парсинге статьи: {e}")
                continue

        logger.info(f"Найдено {len(news_items)} новостей на главной странице")
        return news_items

    def _parse_news_item_from_main(self, article_elem) -> Optional[NewsItem]:
        """
        Парсит элемент новости с главной страницы
        
        Args:
            article_elem: BeautifulSoup элемент статьи
            
        Returns:
            NewsItem объект или None
        """
        try:
            # Извлекаем ID и URL из data-атрибутов
            doc_id = article_elem.get('data-article-docsid')
            article_url = article_elem.get('data-article-url')
            
            if not doc_id or not article_url:
                return None

            # Заголовок
            title_elem = article_elem.find('h2', class_='uho__name rubric_lenta__item_name')
            title = title_elem.get_text(strip=True) if title_elem else "Без названия"

            # Время публикации
            time_elem = article_elem.find('p', class_='uho__tag rubric_lenta__item_tag')
            datetime_str = time_elem.get_text(strip=True) if time_elem else ""

            # Рубрика
            rubric_elem = article_elem.find('a', href=re.compile(r'/rubric/\d+'))
            rubric = rubric_elem.get_text(strip=True) if rubric_elem else "Без рубрики"

            # Автор
            author_elem = article_elem.find('a', href=re.compile(r'/authors/\d+'))
            author = author_elem.get_text(strip=True) if author_elem else None

            # Теги
            tag_elems = article_elem.find_all('a', class_='tag_list__link')
            tags = [tag.get_text(strip=True) for tag in tag_elems] if tag_elems else []

            # URL изображения
            image_url = article_elem.get('data-article-image')

            return NewsItem(
                id=doc_id,
                title=title,
                url=article_url,
                datetime=datetime_str,
                rubric=rubric,
                author=author,
                image_url=image_url,
                tags=tags
            )

        except Exception as e:
            logger.error(f"Ошибка при парсинге элемента новости: {e}")
            return None

    def parse_article(self, url: str) -> Optional[NewsItem]:
        """
        Парсит отдельную статью
        
        Args:
            url: URL статьи
            
        Returns:
            NewsItem объект с полным содержимым или None
        """
        soup = self._make_request(url)
        if not soup:
            return None

        try:
            # Извлекаем ID из URL
            doc_id_match = re.search(r'/doc/(\d+)', url)
            doc_id = doc_id_match.group(1) if doc_id_match else str(hash(url))

            # Заголовок
            title_elem = soup.find('h1', class_='doc_header__name')
            title = title_elem.get_text(strip=True) if title_elem else "Без названия"

            # Время публикации
            time_elem = soup.find('time', class_='doc_header__publish_time')
            datetime_str = ""
            if time_elem:
                datetime_attr = time_elem.get('datetime')
                if datetime_attr:
                    datetime_str = datetime_attr
                else:
                    datetime_str = time_elem.get_text(strip=True)

            # Основной текст статьи
            content_elem = soup.find('div', class_='doc__body')
            content = ""
            if content_elem:
                # Извлекаем все параграфы с текстом
                text_paragraphs = content_elem.find_all('p', class_='doc__text')
                content_parts = []
                for p in text_paragraphs:
                    # Убираем HTML теги и извлекаем чистый текст
                    text = p.get_text(strip=True)
                    if text:
                        content_parts.append(text)
                content = "\n\n".join(content_parts)

            # Рубрика из breadcrumbs или meta
            rubric = "Без рубрики"
            rubric_meta = soup.find('meta', attrs={'name': 'mywidget:category'})
            if rubric_meta:
                rubric = rubric_meta.get('content', 'Без рубрики')

            # Описание из meta
            description = ""
            desc_meta = soup.find('meta', attrs={'name': 'description'})
            if desc_meta:
                description = desc_meta.get('content', '')

            # URL изображения из Open Graph
            image_url = ""
            og_image = soup.find('meta', property='og:image')
            if og_image:
                image_url = og_image.get('content', '')

            return NewsItem(
                id=doc_id,
                title=title,
                url=url,
                datetime=datetime_str,
                rubric=rubric,
                description=description,
                image_url=image_url,
                content=content
            )

        except Exception as e:
            logger.error(f"Ошибка при парсинге статьи {url}: {e}")
            return None

    def get_article_content(self, news_item: NewsItem) -> Optional[str]:
        """
        Получает полный текст статьи для объекта NewsItem
        
        Args:
            news_item: Объект NewsItem
            
        Returns:
            Текст статьи или None
        """
        full_article = self.parse_article(news_item.url)
        return full_article.content if full_article else None

    def parse_multiple_articles(self, urls: List[str]) -> List[NewsItem]:
        """
        Парсит несколько статей
        
        Args:
            urls: Список URL статей
            
        Returns:
            Список объектов NewsItem
        """
        articles = []
        for url in urls:
            article = self.parse_article(url)
            if article:
                articles.append(article)
                
        return articles

    def search_news(self, query: str, limit: int = 20) -> List[NewsItem]:
        """
        Поиск новостей по ключевому слову
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            
        Returns:
            Список найденных новостей
        """
        search_url = f"{self.base_url}/search"
        params = {
            'text': query,
            'sort': 'date'
        }
        
        try:
            response = self.session.get(search_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем результаты поиска
            results = []
            search_items = soup.find_all('article', class_='search_results__item')[:limit]
            
            for item in search_items:
                try:
                    link_elem = item.find('a', class_='search_results__item_name')
                    if link_elem:
                        article_url = urljoin(self.base_url, link_elem.get('href'))
                        article = self.parse_article(article_url)
                        if article:
                            results.append(article)
                except Exception as e:
                    logger.error(f"Ошибка при парсинге результата поиска: {e}")
                    continue
                    
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при поиске: {e}")
            return []

    def save_to_json(self, news_items: List[NewsItem], filename: str):
        """
        Сохраняет новости в JSON файл
        
        Args:
            news_items: Список новостей
            filename: Имя файла
        """
        data = []
        for item in news_items:
            data.append({
                'id': item.id,
                'title': item.title,
                'url': item.url,
                'datetime': item.datetime,
                'rubric': item.rubric,
                'author': item.author,
                'description': item.description,
                'image_url': item.image_url,
                'content': item.content,
                'tags': item.tags
            })
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Сохранено {len(news_items)} новостей в {filename}")

    def save_to_csv(self, news_items: List[NewsItem], filename: str):
        """
        Сохраняет новости в CSV файл
        
        Args:
            news_items: Список новостей
            filename: Имя файла
        """
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Заголовок', 'URL', 'Дата/время', 'Рубрика', 'Автор', 'Описание', 'Содержание'])
            
            for item in news_items:
                writer.writerow([
                    item.id,
                    item.title,
                    item.url,
                    item.datetime,
                    item.rubric,
                    item.author or '',
                    item.description or '',
                    item.content or ''
                ])
        
        logger.info(f"Сохранено {len(news_items)} новостей в {filename}")

    def get_rubric_news(self, rubric_id: int, limit: int = 50) -> List[NewsItem]:
        """
        Получает новости определенной рубрики
        
        Args:
            rubric_id: ID рубрики
            limit: Максимальное количество новостей
            
        Returns:
            Список новостей рубрики
        """
        rubric_url = f"{self.base_url}/rubric/{rubric_id}"
        soup = self._make_request(rubric_url)
        
        if not soup:
            return []
            
        news_items = []
        articles = soup.find_all('article', class_='uho rubric_lenta__item js-article')[:limit]
        
        for article in articles:
            news_item = self._parse_news_item_from_main(article)
            if news_item:
                news_items.append(news_item)
                
        return news_items


def main():
    """Пример использования парсера"""
    # Создаем парсер с задержкой 1 секунда между запросами
    parser = KommersantParser(delay=1.0)
    
    print("🗞️  Парсер сайта Коммерсант")
    print("=" * 50)
    
    # 1. Парсим главную страницу
    print("📰 Парсинг главной страницы...")
    main_news = parser.parse_main_page()
    
    if main_news:
        print(f"✅ Найдено {len(main_news)} новостей")
        
        # Показываем первые 5 новостей
        print("\n🔥 Последние новости:")
        for i, news in enumerate(main_news[:5], 1):
            print(f"{i}. {news.title}")
            print(f"   🕐 {news.datetime} | 📂 {news.rubric}")
            if news.author:
                print(f"   ✍️  {news.author}")
            print()
        
        # 2. Получаем полный текст первой новости
        if main_news:
            print("📖 Получаем полный текст первой новости...")
            full_article = parser.parse_article(main_news[0].url)
            
            if full_article and full_article.content:
                print("✅ Текст получен:")
                print(f"📝 {full_article.content[:200]}...")
            else:
                print("❌ Не удалось получить текст статьи")
        
        # 3. Сохраняем в файлы
        parser.save_to_json(main_news, 'kommersant_news.json')
        parser.save_to_csv(main_news[:10], 'kommersant_news.csv')
        
    else:
        print("❌ Не удалось получить новости")

    # 4. Пример поиска
    print("\n🔍 Поиск новостей по слову 'Путин'...")
    search_results = parser.search_news('Путин', limit=5)
    
    if search_results:
        print(f"✅ Найдено {len(search_results)} результатов")
        for i, news in enumerate(search_results, 1):
            print(f"{i}. {news.title}")
    else:
        print("❌ Результаты поиска не найдены")

    # 5. Пример получения новостей рубрики "Политика" (ID: 1)
    print("\n🏛️  Получаем новости рубрики 'Общество'...")
    rubric_news = parser.get_rubric_news(7, limit=10)  # ID рубрики Общество = 7
    
    if rubric_news:
        print(f"✅ Найдено {len(rubric_news)} новостей в рубрике")
        for i, news in enumerate(rubric_news[:3], 1):
            print(f"{i}. {news.title}")
    else:
        print("❌ Новости рубрики не найдены")


if __name__ == "__main__":
    main() 