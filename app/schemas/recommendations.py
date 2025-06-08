from pydantic import BaseModel
from typing import Optional


class RecommendationResponse(BaseModel):
    buy: bool
    sell: bool
    confidence: float
    reasoning: str
    ticker: Optional[str] = None
    quantity: Optional[int] = None
