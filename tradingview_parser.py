#!/usr/bin/env python3
"""
TradingView News Parser
Быстрый парсер для извлечения новостей с ru.tradingview.com/news/markets/all/
"""

import re
import json
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


@dataclass
class NewsItem:
    """Структура для хранения новости"""
    id: str
    title: str
    story_path: str
    published: int
    published_datetime: str
    urgency: int
    link: Optional[str]
    provider: Dict[str, Any]
    related_symbols: List[Dict[str, Any]]
    permission: Optional[str] = None


class TradingViewParser:
    """
    Быстрый парсер новостей TradingView
    """
    
    def __init__(self, timeout: int = 10):
        """
        Инициализация парсера
        
        Args:
            timeout: Таймаут для HTTP запросов в секундах
        """
        self.base_url = "https://ru.tradingview.com/news/markets/all/"
        self.timeout = timeout
        self.session = requests.Session()
        
        # Настройка заголовков для имитации браузера
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _extract_json_from_script(self, html_content: str) -> Optional[Dict[str, Any]]:
        """
        Извлечение JSON данных из script тегов
        
        Args:
            html_content: HTML контент страницы
            
        Returns:
            Словарь с данными или None
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Ищем script теги с type="application/prs.init-data+json"
            script_tags = soup.find_all('script', type='application/prs.init-data+json')
            
            for script in script_tags:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        
                        # Ищем данные о новостях
                        if self._has_news_data(data):
                            return data
                            
                    except json.JSONDecodeError as e:
                        self.logger.debug(f"Ошибка парсинга JSON в script теге: {e}")
                        continue
                        
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения JSON из HTML: {e}")
            return None

    def _has_news_data(self, data: Dict[str, Any]) -> bool:
        """
        Проверка, содержит ли JSON данные о новостях
        
        Args:
            data: JSON данные
            
        Returns:
            True если содержит новости
        """
        try:
            # Ищем структуру с новостями
            for key, value in data.items():
                if isinstance(value, dict):
                    if 'data' in value and 'news' in value['data']:
                        if 'data' in value['data']['news'] and 'items' in value['data']['news']['data']:
                            return True
            return False
        except:
            return False

    def _parse_news_data(self, json_data: Dict[str, Any]) -> List[NewsItem]:
        """
        Парсинг новостей из JSON данных
        
        Args:
            json_data: JSON данные с новостями
            
        Returns:
            Список объектов NewsItem
        """
        news_items = []
        
        try:
            # Поиск новостей в JSON структуре
            for key, value in json_data.items():
                if isinstance(value, dict) and 'data' in value:
                    data = value['data']
                    if 'news' in data and 'data' in data['news']:
                        news_data = data['news']['data']
                        if 'items' in news_data:
                            items = news_data['items']
                            
                            for item in items:
                                try:
                                    # Преобразование timestamp в читаемый формат
                                    published_dt = datetime.fromtimestamp(item['published'])
                                    published_str = published_dt.strftime('%Y-%m-%d %H:%M:%S')
                                    
                                    news_item = NewsItem(
                                        id=item.get('id', ''),
                                        title=item.get('title', ''),
                                        story_path=item.get('storyPath', ''),
                                        published=item.get('published', 0),
                                        published_datetime=published_str,
                                        urgency=item.get('urgency', 0),
                                        link=item.get('link'),
                                        provider=item.get('provider', {}),
                                        related_symbols=item.get('relatedSymbols', []),
                                        permission=item.get('permission')
                                    )
                                    
                                    news_items.append(news_item)
                                    
                                except Exception as e:
                                    self.logger.warning(f"Ошибка парсинга новости: {e}")
                                    continue
                            break
                            
        except Exception as e:
            self.logger.error(f"Ошибка парсинга данных новостей: {e}")
            
        return news_items

    def get_news(self, limit: int = 10) -> List[NewsItem]:
        """
        Получение первых N новостей с TradingView
        
        Args:
            limit: Количество новостей для извлечения (по умолчанию 10)
            
        Returns:
            Список объектов NewsItem
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Загрузка страницы: {self.base_url}")
            
            # Загрузка страницы
            response = self.session.get(self.base_url, timeout=self.timeout)
            response.raise_for_status()
            
            self.logger.info(f"Страница загружена за {time.time() - start_time:.2f} сек")
            
            # Извлечение JSON данных
            json_data = self._extract_json_from_script(response.text)
            
            if not json_data:
                self.logger.error("Не удалось найти JSON данные с новостями")
                return []
            
            # Парсинг новостей
            news_items = self._parse_news_data(json_data)
            
            if not news_items:
                self.logger.warning("Новости не найдены в JSON данных")
                return []
            
            # Ограничиваем количество новостей
            limited_news = news_items[:limit]
            
            self.logger.info(f"Успешно извлечено {len(limited_news)} новостей за {time.time() - start_time:.2f} сек")
            
            return limited_news
            
        except requests.RequestException as e:
            self.logger.error(f"Ошибка HTTP запроса: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка: {e}")
            return []

    def get_news_as_dict(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получение новостей в виде словарей
        
        Args:
            limit: Количество новостей для извлечения
            
        Returns:
            Список словарей с данными новостей
        """
        news_items = self.get_news(limit)
        
        return [
            {
                'id': item.id,
                'title': item.title,
                'story_path': item.story_path,
                'published': item.published,
                'published_datetime': item.published_datetime,
                'urgency': item.urgency,
                'link': item.link,
                'provider': item.provider,
                'related_symbols': item.related_symbols,
                'permission': item.permission
            }
            for item in news_items
        ]

    def print_news(self, limit: int = 10) -> None:
        """
        Вывод новостей в консоль
        
        Args:
            limit: Количество новостей для вывода
        """
        news_items = self.get_news(limit)
        
        if not news_items:
            print("❌ Новости не найдены")
            return
        
        print(f"\n📰 TradingView - Последние {len(news_items)} новостей:")
        print("=" * 80)
        
        for i, news in enumerate(news_items, 1):
            print(f"\n{i}. {news.title}")
            print(f"   📅 {news.published_datetime}")
            print(f"   🏢 {news.provider.get('name', 'N/A')}")
            if news.link:
                print(f"   🔗 {news.link}")
            if news.related_symbols:
                symbols = [s.get('symbol', 'N/A') for s in news.related_symbols[:3]]
                print(f"   📊 Символы: {', '.join(symbols)}")
            print(f"   🔗 TradingView: https://ru.tradingview.com{news.story_path}")


def main():
    """Пример использования парсера"""
    
    print("🚀 TradingView News Parser")
    print("=" * 50)
    
    try:
        # Создание экземпляра парсера
        parser = TradingViewParser(timeout=15)
        
        # Получение и вывод новостей
        print("\n📡 Подключение к TradingView...")
        parser.print_news(limit=10)
        
        # Получение новостей в виде словарей для дальнейшей обработки
        print("\n🔄 Получение данных в формате словарей...")
        news_dict = parser.get_news_as_dict(limit=5)
        
        print(f"\n✅ Получено {len(news_dict)} новостей в виде словарей")
        
        # Сохранение в JSON файл
        if news_dict:
            with open('tradingview_news.json', 'w', encoding='utf-8') as f:
                json.dump(news_dict, f, ensure_ascii=False, indent=2)
            print("💾 Новости сохранены в tradingview_news.json")
        else:
            print("❌ Нет данных для сохранения")
    
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 