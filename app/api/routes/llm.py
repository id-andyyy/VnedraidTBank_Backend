from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
import json
import logging
from typing import Optional, List

from app.models.llm import LLMResponse, LLMRequest

# Настройка логгера
logger = logging.getLogger(__name__)

llm_router = APIRouter(prefix="/api/llm", tags=["Нейросеть"])


def generate_response_sync(prompt, model="deepseek-ai/DeepSeek-V3-0324", max_tokens=2024, temperature=0.7, role="user"):
    api_key = 'cpk_b9f646794b554414935934ec5a3513de.f78245306f06593ea49ef7bce2228c8e.kHJVJjyK8dtqB0oD2Ofv4AaME6MSnKDy'
    url = 'https://llm.chutes.ai/v1/chat/completions'

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    data = {
        'model': model,
        'messages': [
            {
                'role': role,
                'content': prompt
            }
        ],
        'stream': True,
        'max_tokens': max_tokens,
        'temperature': temperature
    }

    full_response = ""
    response = requests.post(url, headers=headers, json=data, stream=True)
    for line in response.iter_lines():
        if line:
            try:
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    line_text = line_text[6:]
                if line_text.strip() and line_text != '[DONE]':
                    parsed = json.loads(line_text)
                    content = parsed.get('choices', [{}])[0].get('delta', {}).get('content', '')
                    if content:
                        full_response += content
            except json.JSONDecodeError:
                if line_text.strip() == '[DONE]':
                    break
                continue
            except Exception as e:
                logger.error(f"Error parsing LLM response: {str(e)}")
                continue

    return full_response


@llm_router.post('', response_model=LLMResponse)
def llm_endpoint(request: LLMRequest):
    try:
        import time

        start_time = time.time()
        full_response = generate_response_sync(
            prompt=request.prompt,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            role=request.role
        )
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"LLM request completed in {execution_time:.2f} seconds")
        return LLMResponse(
            response=full_response,
            execution_time=execution_time
        )
    except Exception as e:
        logger.error(f"Error in LLM endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing LLM request: {str(e)}")
