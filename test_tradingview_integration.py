#!/usr/bin/env python3
"""
Тест интеграции TradingView парсера в систему
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.parserTradingView import get_news_data

def test_tradingview_parser():
    """Тестируем TradingView парсер"""
    print("🧪 Тестирование TradingView парсера...")
    print("=" * 50)
    
    # Получаем новости
    news_data = get_news_data()
    
    if news_data:
        print(f"✅ Успешно получено {len(news_data)} новостей")
        print("\n📋 Первые 3 новости:")
        
        for i, news in enumerate(news_data[:3], 1):
            print(f"\n{i}. 📰 {news['title']}")
            print(f"   📄 Описание: {news['full_text'][:200]}...")
            print("-" * 80)
    else:
        print("❌ Не удалось получить новости")

if __name__ == "__main__":
    test_tradingview_parser() 