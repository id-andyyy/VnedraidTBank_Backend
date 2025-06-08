#!/usr/bin/env python3
"""
Пример использования TradingView Parser
Демонстрирует различные способы использования парсера
"""

from tradingview_parser import TradingViewParser
import json


def main():
    """Примеры использования парсера"""
    
    print("🔥 TradingView Parser - Примеры использования")
    print("=" * 60)
    
    # Создание экземпляра парсера
    parser = TradingViewParser(timeout=10)
    
    # Пример 1: Простое получение новостей
    print("\n📊 Пример 1: Получение первых 5 новостей")
    print("-" * 40)
    
    news_items = parser.get_news(limit=5)
    
    if news_items:
        for i, news in enumerate(news_items, 1):
            print(f"{i}. {news.title}")
            print(f"   Время: {news.published_datetime}")
            print(f"   Источник: {news.provider.get('name', 'N/A')}")
            print()
    else:
        print("❌ Новости не найдены")
    
    # Пример 2: Получение данных в формате словарей
    print("\n🗂️ Пример 2: Данные в формате словарей")
    print("-" * 40)
    
    news_dict = parser.get_news_as_dict(limit=3)
    
    if news_dict:
        print(f"Получено {len(news_dict)} новостей:")
        for i, news in enumerate(news_dict, 1):
            print(f"{i}. {news['title'][:50]}...")
            print(f"   ID: {news['id']}")
            print(f"   Символы: {len(news['related_symbols'])} шт.")
            print()
    
    # Пример 3: Фильтрация новостей по провайдеру
    print("\n🔍 Пример 3: Фильтрация по провайдерам")
    print("-" * 40)
    
    all_news = parser.get_news(limit=20)
    
    if all_news:
        # Группировка по провайдерам
        providers = {}
        for news in all_news:
            provider_name = news.provider.get('name', 'Unknown')
            if provider_name not in providers:
                providers[provider_name] = []
            providers[provider_name].append(news)
        
        print("Провайдеры новостей:")
        for provider, provider_news in providers.items():
            print(f"  • {provider}: {len(provider_news)} новостей")
    
    # Пример 4: Анализ связанных символов
    print("\n📈 Пример 4: Анализ связанных символов")
    print("-" * 40)
    
    if all_news:
        symbols = []
        for news in all_news:
            for symbol_data in news.related_symbols:
                symbol = symbol_data.get('symbol', '')
                if symbol:
                    symbols.append(symbol)
        
        # Подсчет самых популярных символов
        from collections import Counter
        symbol_counts = Counter(symbols)
        
        print("Топ-5 самых упоминаемых символов:")
        for symbol, count in symbol_counts.most_common(5):
            print(f"  • {symbol}: {count} раз")
    
    # Пример 5: Сохранение в разных форматах
    print("\n💾 Пример 5: Сохранение данных")
    print("-" * 40)
    
    if news_dict:
        # Сохранение в JSON
        with open('latest_tradingview_news.json', 'w', encoding='utf-8') as f:
            json.dump(news_dict, f, ensure_ascii=False, indent=2)
        print("✅ Данные сохранены в latest_tradingview_news.json")
        
        # Сохранение в текстовый файл
        with open('latest_tradingview_news.txt', 'w', encoding='utf-8') as f:
            f.write("TradingView News Summary\n")
            f.write("=" * 50 + "\n\n")
            
            for i, news in enumerate(news_dict, 1):
                f.write(f"{i}. {news['title']}\n")
                f.write(f"   Time: {news['published_datetime']}\n")
                f.write(f"   Source: {news['provider'].get('name', 'N/A')}\n")
                if news['link']:
                    f.write(f"   Link: {news['link']}\n")
                f.write("\n")
        
        print("✅ Данные сохранены в latest_tradingview_news.txt")


if __name__ == "__main__":
    main() 