from app.db.base import Base


class LLMRequest(Base):
    prompt: str
    model: str = "deepseek-ai/DeepSeek-V3-0324"
    max_tokens: int = 2024
    temperature: float = 0.7
    role: str = "user"


class LLMResponse(Base):
    response: str
    execution_time: float
