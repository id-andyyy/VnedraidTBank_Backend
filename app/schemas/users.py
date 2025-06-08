from pydantic import BaseModel


class UserInteractionRequest(BaseModel):
    news_id: int


class AddTickerRequest(BaseModel):
    company_id: int
