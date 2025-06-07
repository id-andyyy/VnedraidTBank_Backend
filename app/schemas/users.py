from pydantic import BaseModel


class UserInteractionRequest(BaseModel):
    news_id: int
