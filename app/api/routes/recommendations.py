import json
import logging
from typing import Optional, Dict, Any, List

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.core.constants import TAG_MAP
from app.models import User
from app.models.news import NewsArticle
from app.schemas.recommendations import RecommendationResponse, NewsAssistantRequest, NewsAssistantResponse

LLM_API_KEY = 'cpk_b9f646794b554414935934ec5a3513de.f78245306f06593ea49ef7bce2228c8e.kHJVJjyK8dtqB0oD2Ofv4AaME6MSnKDy'
LLM_URL = 'https://llm.chutes.ai/v1/chat/completions'
# Предполагаемый базовый URL API для инвестиций
INVEST_API_URL = "https://invest-api.chutes.ai"

recommendation_router = APIRouter()
logger = logging.getLogger(__name__)


def _generate_llm_json_response(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Выполняет вызов к LLM API для получения ответа в формате JSON.
    """
    headers = {
        'Authorization': f'Bearer {LLM_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': "deepseek-ai/DeepSeek-V3-0324",
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
        'max_tokens': 1024,
        'temperature': 0.2,
        'response_format': {'type': 'json_object'}
    }

    try:
        response = requests.post(
            LLM_URL, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        response_data = response.json()
        content_str = response_data['choices'][0]['message']['content']
        return json.loads(content_str)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к LLM API для рекомендации: {e}")
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Ошибка парсинга JSON ответа от LLM: {e}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в LLM API: {e}")

    return None


def _get_user_trade_operations(user: User) -> List[Dict[str, Any]]:
    """
    Получает последние торговые операции пользователя.
    """
    if not user.invest_token:
        return []

    try:
        url = f"{INVEST_API_URL}/sandbox/operations"
        headers = {"Authorization": f"Bearer {user.invest_token}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json().get("operations", [])
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Не удалось получить торговые операции для пользователя {user.id}: {e}")
        return []


def _build_llm_prompt(
    news_article: NewsArticle,
    user_context: Dict[str, Any]
) -> str:
    """
    Создает промпт для LLM на основе новости и данных пользователя.
    """
    return f"""
Ты — опытный финансовый аналитик. Твоя задача — проанализировать новость и предоставить инвестиционную рекомендацию для пользователя.

**Контекст:**

**Новость:**
- Заголовок: {news_article.title}
- Текст: {news_article.full_text}
- Теги новости: {news_article.tags}
- Тикеры, упомянутые в новости: {news_article.tickers}

**Профиль пользователя:**
- Любимые теги (высокий интерес): {', '.join(user_context['loved_tags']) if user_context['loved_tags'] else 'Нет'}
- Нейтральные теги (средний интерес): {', '.join(user_context['neutral_tags']) if user_context['neutral_tags'] else 'Нет'}
- Нелюбимые теги (низкий интерес): {', '.join(user_context['unloved_tags']) if user_context['unloved_tags'] else 'Нет'}
- Отслеживаемые тикеры: {', '.join(user_context['favorite_tickers']) if user_context['favorite_tickers'] else 'Нет'}

**Недавние операции пользователя:**
{json.dumps(user_context['operations'], indent=2, ensure_ascii=False) if user_context['operations'] else 'Нет недавних операций.'}

**Твоя задача:**

Проанализируй всю предоставленную информацию и прими решение: стоит ли покупать, продавать или держать акции, связанные с этой новостью.

**Требования к ответу:**

Верни ответ СТРОГО в формате JSON со следующими полями:
- "action": одно из трёх строковых значений: "buy", "sell" или "hold".
- "ticker": тикер компании для операции (если action 'buy' или 'sell'). Если 'hold', это поле должно быть null. Выбери наиболее релевантный тикер из новости.
- "confidence": число от 0 до 100, представляющее твою уверенность в рекомендации.
- "reasoning": краткое объяснение твоего решения (1-2 предложения) на русском языке.
- "quantity": рекомендуемое количество лотов/акций для покупки/продажи. Рассчитай это как небольшое целое число (например, 1-10), основываясь на значимости новости.

Если информации хоть немного хвататет на принятие решения о покупке или продаже, то лучше предложи продать или купить, чем держать.

**Пример ответа:**
{{
  "action": "buy",
  "ticker": "SBER",
  "confidence": 85.0,
  "reasoning": "Новость позитивна для банковского сектора, и Сбербанк является ключевым игроком. Это хорошая точка для входа.",
  "quantity": 5
}}

**Твой JSON ответ:**
"""


@recommendation_router.post(
    "/recommendations/news/{news_id}",
    response_model=RecommendationResponse,
    summary="Получить инвестиционную рекомендацию по новости"
)
def get_recommendation_for_news(
    news_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Анализирует новость и профиль пользователя для создания
    персональной инвестиционной рекомендации с помощью LLM.
    """
    logger.info(
        f"Starting recommendation generation for news_id={news_id}, user_id={current_user.id}")

    news_article = db.query(NewsArticle).filter(
        NewsArticle.id == news_id).first()
    if not news_article:
        logger.warning(
            f"News article with id={news_id} not found for user_id={current_user.id}")
        raise HTTPException(
            status_code=404, detail=f"Новость с ID {news_id} не найдена")

    logger.info(f"Found news article: '{news_article.title}'")

    # 1. Сбор предпочтений пользователя
    logger.info(f"Collecting user preferences for user_id={current_user.id}")
    loved_tags, neutral_tags, unloved_tags = [], [], []
    for field, tag_name in TAG_MAP.items():
        score = getattr(current_user, field, 0)
        if score >= 3:
            loved_tags.append(tag_name)
        elif -1 <= score <= 2:
            neutral_tags.append(tag_name)
        else:  # score < -1
            unloved_tags.append(tag_name)

    favorite_tickers = [t.strip() for t in current_user.tickers.split(
        ',')] if current_user.tickers else []
    logger.debug(f"User preferences for user_id={current_user.id}: "
                 f"loved_tags={loved_tags}, neutral_tags={neutral_tags}, "
                 f"unloved_tags={unloved_tags}, favorite_tickers={favorite_tickers}")

    # 2. Сбор истории торгов пользователя
    logger.info(f"Fetching trade history for user_id={current_user.id}")
    operations = _get_user_trade_operations(current_user)
    logger.info(
        f"Found {len(operations)} trade operations for user_id={current_user.id}")

    # 3. Формирование промпта
    logger.info("Building prompt for LLM.")
    user_context = {
        "loved_tags": loved_tags,
        "neutral_tags": neutral_tags,
        "unloved_tags": unloved_tags,
        "favorite_tickers": favorite_tickers,
        "operations": operations
    }
    prompt = _build_llm_prompt(news_article, user_context)
    logger.debug(
        f"Generated prompt for LLM (first 200 chars): {prompt[:200]}...")

    # 4. Получение рекомендации от LLM
    logger.info("Requesting recommendation from LLM.")
    llm_data = _generate_llm_json_response(prompt)
    if not llm_data:
        logger.error(
            f"Failed to get recommendation from LLM for news_id={news_id}")
        raise HTTPException(
            status_code=500, detail="Ошибка при получении рекомендации от языковой модели.")

    logger.info(f"Received LLM response: {llm_data}")

    # 5. Форматирование и возврат ответа
    logger.info("Formatting final response.")
    action = str(llm_data.get("action", "hold")).lower()
    if action not in ["buy", "sell", "hold"]:
        logger.warning(
            f"LLM returned invalid action '{action}'. Defaulting to 'hold'.")
        action = "hold"

    buy = action == "buy"
    sell = action == "sell"
    ticker = llm_data.get("ticker") if buy or sell else None

    response_data = RecommendationResponse(
        buy=buy,
        sell=sell,
        confidence=float(llm_data.get("confidence", 0.0)),
        reasoning=str(llm_data.get(
            "reasoning", "Нет достаточной информации.")),
        ticker=ticker,
        quantity=int(llm_data.get("quantity", 0))
    )

    logger.info(
        f"Successfully generated recommendation for news_id={news_id}. Response: {response_data.json()}")
    return response_data


def _build_assistant_prompt(news_text: str, question: str) -> str:
    """
    Создает промпт для LLM-ассистента по новостям.
    """
    return f"""
Ты — полезный ассистент, который помогает пользователям понять новостные статьи.
Твоя задача — ответить на вопрос пользователя, основываясь ИСКЛЮЧИТЕЛЬНО на тексте предоставленной новости.
Не придумывай информацию и не используй свои общие знания. Если ответ на вопрос не содержится в тексте, прямо сообщи об этом.

**Текст новости:**
---
{news_text}
---

**Вопрос пользователя:**
{question}

**Твой ответ:**
"""


def _generate_assistant_response(prompt: str) -> str:
    """
    Выполняет вызов к LLM API для получения текстового ответа.
    """
    headers = {
        'Authorization': f'Bearer {LLM_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': "deepseek-ai/DeepSeek-V3-0324",
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
        'max_tokens': 1500,
        'temperature': 0.3,
    }

    try:
        response = requests.post(
            LLM_URL, headers=headers, json=data, timeout=90)
        response.raise_for_status()
        response_data = response.json()
        answer = response_data['choices'][0]['message']['content']
        return answer.strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к LLM API для ассистента: {e}")
        raise HTTPException(
            status_code=502, detail="Ошибка при обращении к языковой модели.")
    except (KeyError, IndexError) as e:
        logger.error(f"Ошибка парсинга ответа от LLM: {e}")
        raise HTTPException(
            status_code=500, detail="Некорректный ответ от языковой модели.")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в LLM API ассистента: {e}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера.")


@recommendation_router.post(
    "/assistant/ask",
    response_model=NewsAssistantResponse,
    summary="Задать вопрос по тексту новости"
)
def ask_news_assistant(request: NewsAssistantRequest):
    """
    Принимает текст новости и вопрос пользователя, возвращает ответ от LLM.
    """
    logger.info(
        f"Received question for news assistant: '{request.question[:50]}...'")

    prompt = _build_assistant_prompt(request.news_text, request.question)
    logger.debug(f"Built prompt for assistant: {prompt[:200]}...")

    answer = _generate_assistant_response(prompt)
    logger.info("Successfully generated answer from assistant.")

    return NewsAssistantResponse(answer=answer)
