#!/usr/bin/env python3
"""
Telegram News Parser - Парсер новостей из Telegram каналов
"""

import asyncio
import logging
import json
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    from telethon import TelegramClient, events
    from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
    from telethon.errors import SessionPasswordNeededError, ChannelPrivateError, FloodWaitError
except ImportError:
    print("❌ Ошибка: Установите telethon: pip install telethon")
    exit(1)

try:
    import aiofiles
except ImportError:
    print("❌ Ошибка: Установите aiofiles: pip install aiofiles")
    exit(1)

from pydantic import BaseModel, Field

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TelegramNews:
    """Модель новости из Telegram"""
    channel_username: str
    channel_title: str
    message_id: int
    text: str
    date: datetime
    views: Optional[int] = None
    forwards: Optional[int] = None
    media_urls: List[str] = None
    media_type: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = None
    category: Optional[str] = None
    
    def __post_init__(self):
        if self.media_urls is None:
            self.media_urls = []
        if self.tags is None:
            self.tags = []


class TelegramParserConfig(BaseModel):
    """Конфигурация парсера"""
    api_id: int = Field(..., description="Telegram API ID")
    api_hash: str = Field(..., description="Telegram API Hash")
    phone_number: str = Field(..., description="Номер телефона")
    session_name: str = Field(default="telegram_parser", description="Имя сессии")
    
    # Каналы для мониторинга
    channels: List[str] = Field(
        default=[
            "@breakingmash",
            "@RIANovosti", 
            "@tass_agency",
            "@rbc_news",
            "@vedomosti"
        ],
        description="Список каналов для парсинга"
    )
    
    # Фильтры
    keywords: List[str] = Field(
        default=["экономика", "финансы", "рынок", "биржа", "валюта", "инвестиции", "банк"],
        description="Ключевые слова для фильтрации"
    )
    exclude_keywords: List[str] = Field(
        default=["реклама", "спам"],
        description="Исключающие ключевые слова"
    )
    
    # Параметры парсинга
    max_messages: int = Field(default=100, description="Максимум сообщений за раз")
    hours_back: int = Field(default=24, description="Сколько часов назад искать")
    download_media: bool = Field(default=False, description="Скачивать медиа")
    media_dir: str = Field(default="media", description="Папка для медиа")


class TelegramNewsParser:
    """Основной класс парсера Telegram новостей"""
    
    def __init__(self, config: TelegramParserConfig):
        self.config = config
        self.client = None
        self.media_dir = Path(config.media_dir)
        self.media_dir.mkdir(exist_ok=True)
        
        # Статистика
        self.stats = {
            "total_processed": 0,
            "filtered_out": 0,
            "saved": 0,
            "errors": 0
        }
        
    async def initialize(self):
        """Инициализация клиента"""
        try:
            self.client = TelegramClient(
                self.config.session_name,
                self.config.api_id,
                self.config.api_hash
            )
            
            await self.client.start(phone=self.config.phone_number)
            logger.info("✅ Telegram клиент успешно инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            raise
    
    async def close(self):
        """Закрытие соединений"""
        if self.client:
            await self.client.disconnect()
    
    def _filter_message(self, text: str) -> bool:
        """Фильтрация сообщения по ключевым словам"""
        if not text:
            return False
            
        text_lower = text.lower()
        
        # Проверяем исключающие слова
        for exclude_word in self.config.exclude_keywords:
            if exclude_word.lower() in text_lower:
                return False
        
        # Проверяем включающие слова
        if not self.config.keywords:
            return True
            
        for keyword in self.config.keywords:
            if keyword.lower() in text_lower:
                return True
                
        return False
    
    def _extract_tags(self, text: str) -> List[str]:
        """Извлечение хештегов"""
        return re.findall(r'#(\w+)', text)
    
    def _categorize_news(self, text: str) -> str:
        """Категоризация новостей"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["экономика", "рынок", "биржа", "валюта"]):
            return "экономика"
        elif any(word in text_lower for word in ["политика", "выборы", "правительство"]):
            return "политика"
        elif any(word in text_lower for word in ["технологии", "it", "интернет"]):
            return "технологии"
        elif any(word in text_lower for word in ["спорт", "футбол", "хоккей"]):
            return "спорт"
        else:
            return "общие"
    
    async def _download_media(self, message, media_urls: List[str]) -> List[str]:
        """Скачивание медиа-файлов"""
        if not self.config.download_media or not message.media:
            return media_urls
            
        try:
            media_path = self.media_dir / f"{message.id}"
            media_path.mkdir(exist_ok=True)
            
            if isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument)):
                file_path = await self.client.download_media(
                    message.media, 
                    file=str(media_path)
                )
                if file_path:
                    media_urls.append(str(file_path))
                    
        except Exception as e:
            logger.error(f"Ошибка скачивания медиа {message.id}: {e}")
            
        return media_urls
    
    async def _process_message(self, message, channel_info: Dict) -> Optional[TelegramNews]:
        """Обработка сообщения"""
        try:
            text = message.text or ""
            
            # Фильтрация
            if not self._filter_message(text):
                self.stats["filtered_out"] += 1
                return None
            
            # Определение типа медиа
            media_type = None
            media_urls = []
            
            if message.media:
                if isinstance(message.media, MessageMediaPhoto):
                    media_type = "photo"
                elif isinstance(message.media, MessageMediaDocument):
                    media_type = "document"
                
                media_urls = await self._download_media(message, media_urls)
            
            # Создание объекта новости
            news = TelegramNews(
                channel_username=channel_info["username"],
                channel_title=channel_info["title"],
                message_id=message.id,
                text=text,
                date=message.date.replace(tzinfo=timezone.utc),
                views=getattr(message, 'views', None),
                forwards=getattr(message, 'forwards', None),
                media_urls=media_urls,
                media_type=media_type,
                author=getattr(message, 'post_author', None),
                tags=self._extract_tags(text),
                category=self._categorize_news(text)
            )
            
            self.stats["total_processed"] += 1
            return news
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения {message.id}: {e}")
            self.stats["errors"] += 1
            return None
    
    async def parse_channel(self, channel_username: str) -> List[TelegramNews]:
        """Парсинг отдельного канала"""
        news_list = []
        
        try:
            # Получение информации о канале
            channel = await self.client.get_entity(channel_username)
            channel_info = {
                "username": channel_username,
                "title": getattr(channel, 'title', channel_username),
                "id": channel.id
            }
            
            logger.info(f"📺 Парсинг канала: {channel_info['title']} ({channel_username})")
            
            # Временные рамки
            date_from = datetime.now(timezone.utc) - timedelta(hours=self.config.hours_back)
            
            # Получение сообщений
            async for message in self.client.iter_messages(
                channel,
                limit=self.config.max_messages,
                offset_date=date_from
            ):
                if message.date < date_from:
                    break
                    
                news = await self._process_message(message, channel_info)
                if news:
                    news_list.append(news)
            
            logger.info(f"✅ Канал {channel_username}: получено {len(news_list)} новостей")
            
        except ChannelPrivateError:
            logger.error(f"❌ Канал {channel_username} приватный или недоступен")
        except FloodWaitError as e:
            logger.warning(f"⏰ Rate limit для {channel_username}, ждем {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга канала {channel_username}: {e}")
            self.stats["errors"] += 1
        
        return news_list
    
    async def save_to_json(self, news_list: List[TelegramNews], filename: str = None):
        """Сохранение в JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"telegram_news_{timestamp}.json"
        
        try:
            # Конвертация в словари
            news_dicts = []
            for news in news_list:
                news_dict = asdict(news)
                news_dict['date'] = news.date.isoformat()
                news_dicts.append(news_dict)
            
            # Асинхронная запись
            async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(news_dicts, ensure_ascii=False, indent=2))
            
            logger.info(f"💾 Новости сохранены в файл: {filename}")
            self.stats["saved"] += len(news_list)
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в JSON: {e}")
    
    async def parse_all_channels(self) -> List[TelegramNews]:
        """Парсинг всех каналов"""
        all_news = []
        
        for channel in self.config.channels:
            try:
                channel_news = await self.parse_channel(channel)
                all_news.extend(channel_news)
                
                # Пауза между каналами
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Ошибка канала {channel}: {e}")
        
        # Сортировка по дате
        all_news.sort(key=lambda x: x.date, reverse=True)
        
        return all_news
    
    def print_stats(self):
        """Статистика"""
        logger.info("📊 === СТАТИСТИКА ПАРСИНГА ===")
        logger.info(f"📝 Всего обработано: {self.stats['total_processed']}")
        logger.info(f"🚫 Отфильтровано: {self.stats['filtered_out']}")
        logger.info(f"💾 Сохранено: {self.stats['saved']}")
        logger.info(f"❌ Ошибок: {self.stats['errors']}")


# Основная функция
async def parse_telegram_news(config: TelegramParserConfig) -> List[TelegramNews]:
    """Главная функция парсинга"""
    parser = TelegramNewsParser(config)
    
    try:
        await parser.initialize()
        news_list = await parser.parse_all_channels()
        
        # Сохранение результатов
        await parser.save_to_json(news_list)
        
        parser.print_stats()
        return news_list
        
    finally:
        await parser.close()


# Пример использования
async def main():
    """Пример запуска"""
    
    # Конфигурация (замените на свои данные!)
    config = TelegramParserConfig(
        api_id=12345,  # ⚠️ ЗАМЕНИТЕ на ваш API ID
        api_hash="your_api_hash",  # ⚠️ ЗАМЕНИТЕ на ваш API Hash
        phone_number="+7XXXXXXXXXX",  # ⚠️ ЗАМЕНИТЕ на ваш номер
        channels=[
            "@breakingmash",
            "@RIANovosti",
            "@tass_agency"
        ],
        keywords=["экономика", "финансы", "рынок", "биржа"],
        max_messages=50,
        hours_back=12
    )
    
    try:
        news_list = await parse_telegram_news(config)
        print(f"\n🎉 Получено {len(news_list)} новостей")
        
        # Показать примеры
        for i, news in enumerate(news_list[:3], 1):
            print(f"\n📰 Новость {i}:")
            print(f"   📺 Канал: {news.channel_title}")
            print(f"   📅 Дата: {news.date.strftime('%Y-%m-%d %H:%M')}")
            print(f"   📁 Категория: {news.category}")
            print(f"   👁️ Просмотры: {news.views or 'N/A'}")
            print(f"   📝 Текст: {news.text[:200]}{'...' if len(news.text) > 200 else ''}")
            if news.tags:
                print(f"   🏷️ Теги: {', '.join(news.tags)}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка в main: {e}")


if __name__ == "__main__":
    print("🚀 Запуск Telegram News Parser...")
    asyncio.run(main()) 