from pydantic import BaseModel
from typing import Optional


class RecommendationResponse(BaseModel):
    buy: bool
    sell: bool
    confidence: float
    reasoning: str
    ticker: Optional[str] = None
    quantity: Optional[int] = None


class NewsAssistantRequest(BaseModel):
    news_text: str
    question: str


class NewsAssistantResponse(BaseModel):
    answer: str
