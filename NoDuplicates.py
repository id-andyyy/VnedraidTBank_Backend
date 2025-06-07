import json
import numpy as np
from sentence_transformers import SentenceTransformer, util
from annoy import AnnoyIndex # Импортируем Annoy

def deduplicate_news_with_annoy(articles: list, threshold: float = 0.7) -> list:
    """
    Удаляет дубликаты новостей из списка, используя векторизацию и Annoy.

    Args:
        articles (list): Список новостей.
        threshold (float): Порог схожести (от 0 до 1).

    Returns:
        list: Список новостей без дубликатов.
    """
    if not articles:
        return []

    print("Шаг 1: Загрузка модели и векторизация новостей...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    texts_to_vectorize = [f"{article['title']}. {article['full_text']}" for article in articles]
    embeddings = model.encode(texts_to_vectorize, show_progress_bar=True)
    
    dimension = embeddings.shape[1]
    print(f"Векторизация завершена. Размерность вектора: {dimension}")

    print("\nШаг 2: Создание индекса Annoy и поиск дубликатов...")
    
    # Создаем индекс Annoy. 'angular' - это косинусное расстояние.
    annoy_index = AnnoyIndex(dimension, 'angular')

    # Добавляем векторы в индекс
    for i, vector in enumerate(embeddings):
        annoy_index.add_item(i, vector)

    # Строим индекс. 10 деревьев - хороший компромисс между скоростью и точностью.
    annoy_index.build(10) 
    print("Индекс Annoy построен.")

    duplicate_indices = set()
    
    for i in range(len(articles)):
        if i in duplicate_indices:
            continue
        
        # Ищем 5 ближайших соседей. Первый будет сам элемент.
        # include_distances=True вернет и расстояние
        neighbors_indices, neighbor_distances = annoy_index.get_nns_by_item(i, 5, include_distances=True)

        print(f"\nАнализ новости #{i}: '{articles[i]['title'][:50]}...'")
        print(f"Найдено соседей: {len(neighbors_indices)}")

        # Проходим по найденным соседям
        for j in range(1, len(neighbors_indices)):
            neighbor_idx = neighbors_indices[j]
            
            # Annoy возвращает расстояние, а нам нужна схожесть.
            # Для 'angular' схожесть можно рассчитать так, но проще пересчитать честно.
            # Мы можем просто взять векторы и посчитать косинусную схожесть.
            similarity = util.cos_sim(embeddings[i], embeddings[neighbor_idx]).item()
            
            print(f"  Сравнение с новостью #{neighbor_idx}: '{articles[neighbor_idx]['title'][:50]}...'")
            print(f"  Схожесть: {similarity:.4f} (порог: {threshold})")

            if similarity > threshold:
                print(f"  → ДУБЛИКАТ НАЙДЕН!")
                duplicate_indices.add(neighbor_idx)
            else:
                print(f"  → Не дубликат (схожесть {similarity:.4f} < {threshold})")
    
    print(f"\nНайдено дубликатов: {len(duplicate_indices)}")

    # Шаг 3: Формирование нового списка
    cleaned_articles = [article for idx, article in enumerate(articles) if idx not in duplicate_indices]
    
    return cleaned_articles


if __name__ == '__main__':
    try:
        with open('DORA.json', 'r', encoding='utf-8') as f:
            all_news = json.load(f)
    except FileNotFoundError:
        print("Ошибка: Файл 'pox.json' не найден.")
        exit()

    print(f"Исходное количество новостей: {len(all_news)}")
    
    final_news = deduplicate_news_with_annoy(all_news)
    
    print(f"\nКоличество новостей после удаления дубликатов: {len(final_news)}")
    
    print("\n--- Заголовки новостей после очистки ---")
    for article in final_news:
        print(f"- {article['title']}")
        
    with open('pox_deduplicated_annoy.json', 'w', encoding='utf-8') as f:
        json.dump(final_news, f, ensure_ascii=False, indent=4)
    print("\nОчищенный список новостей сохранен в файл 'pox_deduplicated_annoy.json'")