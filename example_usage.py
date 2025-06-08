#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой пример использования парсера Коммерсант
"""

from kommersant_parser import KommersantParser

def simple_example():
    """Простой пример парсинга"""
    print("🚀 Запуск парсера Коммерсант...")
    
    # Создаем парсер
    parser = KommersantParser(delay=0.5)  # Задержка 0.5 секунды
    
    # 1. Получаем последние новости
    print("\n📰 Получаем последние новости...")
    news = parser.parse_main_page()
    
    if news:
        print(f"✅ Получено {len(news)} новостей")
        
        # Показываем топ-3 новости
        for i, article in enumerate(news[:3], 1):
            print(f"\n{i}. {article.title}")
            print(f"   📅 {article.datetime}")
            print(f"   🏷️  {article.rubric}")
            if article.author:
                print(f"   ✍️  {article.author}")
            print(f"   🔗 {article.url}")
    else:
        print("❌ Не удалось получить новости")
        return

    # 2. Получаем полный текст первой статьи
    print(f"\n📖 Получаем полный текст статьи: {news[0].title}")
    full_article = parser.parse_article(news[0].url)
    
    if full_article and full_article.content:
        print("✅ Текст статьи получен:")
        print(f"📝 {full_article.content}")
        print(f"\n📊 Длина текста: {len(full_article.content)} символов")
    else:
        print("❌ Не удалось получить текст статьи")

    # 3. Сохраняем результаты
    print("\n💾 Сохраняем результаты...")
    parser.save_to_json(news[:10], 'latest_news.json')
    parser.save_to_csv(news[:5], 'latest_news.csv')
    print("✅ Результаты сохранены в файлы latest_news.json и latest_news.csv")

def search_example():
    """Пример поиска новостей"""
    print("\n🔍 Пример поиска новостей...")
    
    parser = KommersantParser(delay=0.5)
    
    # Поиск по ключевому слову
    search_query = "экономика"
    print(f"Ищем новости по запросу: '{search_query}'")
    
    results = parser.search_news(search_query, limit=5)
    
    if results:
        print(f"✅ Найдено {len(results)} результатов:")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article.title}")
            print(f"   📅 {article.datetime}")
            print(f"   🔗 {article.url}")
            print()
    else:
        print("❌ Результаты не найдены")

def rubric_example():
    """Пример получения новостей рубрики"""
    print("\n📂 Пример получения новостей рубрики...")
    
    parser = KommersantParser(delay=0.5)
    
    # Получаем новости рубрики "Общество" (ID: 7)
    rubric_news = parser.get_rubric_news(7, limit=5)
    
    if rubric_news:
        print(f"✅ Получено {len(rubric_news)} новостей из рубрики 'Общество':")
        for i, article in enumerate(rubric_news, 1):
            print(f"{i}. {article.title}")
            print(f"   📅 {article.datetime}")
            print()
    else:
        print("❌ Новости рубрики не найдены")

def get_article_with_content():
    """Пример получения статьи с полным содержимым"""
    print("\n📄 Пример получения конкретной статьи...")
    
    parser = KommersantParser(delay=0.5)
    
    # URL конкретной статьи (можно заменить на любой другой)
    article_url = "https://www.kommersant.ru/doc/7794143"
    
    article = parser.parse_article(article_url)
    
    if article:
        print("✅ Статья получена:")
        print(f"📰 Заголовок: {article.title}")
        print(f"📅 Дата: {article.datetime}")
        print(f"🏷️  Рубрика: {article.rubric}")
        print(f"📝 Описание: {article.description}")
        
        if article.content:
            print(f"\n📖 Содержание ({len(article.content)} символов):")
            # Показываем первые 300 символов
            print(article.content[:300] + "..." if len(article.content) > 300 else article.content)
        else:
            print("❌ Содержание статьи не найдено")
    else:
        print("❌ Не удалось получить статью")

if __name__ == "__main__":
    print("🗞️  Примеры использования парсера Коммерсант")
    print("=" * 60)
    
    # Запускаем примеры
    simple_example()
    search_example() 
    rubric_example()
    get_article_with_content()
    
    print("\n🎉 Все примеры выполнены!")
    print("\n💡 Доступные методы парсера:")
    print("   - parse_main_page() - парсинг главной страницы")
    print("   - parse_article(url) - парсинг отдельной статьи")
    print("   - search_news(query) - поиск новостей")
    print("   - get_rubric_news(id) - новости рубрики")
    print("   - save_to_json() / save_to_csv() - сохранение") 