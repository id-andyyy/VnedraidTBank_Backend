from pydantic import BaseModel


class LLMRequest(BaseModel):
    prompt: str
    model: str = "deepseek-ai/DeepSeek-V3-0324"
    max_tokens: int = 2024
    temperature: float = 0.7
    role: str = "user"


class LLMResponse(BaseModel):
    response: str
    execution_time: float
