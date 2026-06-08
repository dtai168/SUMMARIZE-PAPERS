from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentRecord(BaseModel):
    user_id: str
    title: str = Field(min_length=1, max_length=240)
    source_type: Literal["text", "pdf"]
    language: Literal["vi", "en"] = "vi"
    extracted_text: str = Field(min_length=1)
    file_path: str | None = None
    original_filename: str | None = None
    extraction_method: str | None = None
    content_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


class SummaryRecord(BaseModel):
    document_id: str
    summary: str
    method: str
    source: str
    rating_count: int = 0
    rating_total: int = 0
    rating_average: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


class SummaryRatingRecord(BaseModel):
    summary_id: str
    document_id: str
    user_id: str
    rating: Literal[1, 2, 3, 4, 5]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


class ChatMessageRecord(BaseModel):
    user_id: str
    document_id: str
    question: str
    answer: str
    method: str
    source: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(mode="python")
