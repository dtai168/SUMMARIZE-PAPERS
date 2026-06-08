from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    document_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)
    locale: Literal["vi", "en"] = "vi"


class ChatResponse(BaseModel):
    answer: str
    method: str
    source: str
    created_at: datetime


class ChatMessageResponse(BaseModel):
    id: str
    document_id: str
    question: str
    answer: str
    method: str
    source: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    items: list[ChatMessageResponse]
    document_id: str
    limit: int
    total_returned: int
