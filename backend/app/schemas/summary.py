from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UploadDocumentResponse(BaseModel):
    id: str
    title: str
    source_type: Literal["pdf"]
    language: Literal["vi", "en"]
    created_at: datetime
    extraction_method: str | None = None
    reused_existing: bool = False


class SummaryCreateTextRequest(BaseModel):
    text: str = Field(min_length=1)
    language: Literal["vi", "en"] = "vi"
    title: str | None = Field(default=None, max_length=240)


class SummaryGenerateRequest(BaseModel):
    language: Literal["vi", "en"] = "vi"
    force_regenerate: bool = False
    target_words: int | None = Field(default=None, ge=150, le=2000)


class DocumentResponse(BaseModel):
    id: str
    title: str
    source_type: Literal["text", "pdf"]
    language: Literal["vi", "en"]
    created_at: datetime
    extraction_method: str | None = None
    reused_existing: bool = False


class SummaryResponse(BaseModel):
    summary_id: str
    document_id: str
    source: str
    language: Literal["vi", "en"]
    summary: str
    extractive_summary: str | None = None
    word_count: int = 0
    method: str
    debug: dict | None = None
    rating_average: float = 0.0
    rating_count: int = 0
    current_user_rating: int | None = None
    created_at: datetime


class SummaryRateRequest(BaseModel):
    rating: Literal[1, 2, 3, 4, 5]


class SummaryHistoryItem(BaseModel):
    id: str
    title: str
    source_type: Literal["text", "pdf"]
    created_at: datetime
    status: Literal["ready", "processing"]
    has_summary: bool
    extraction_method: str | None = None
    summary_created_at: datetime | None = None
    summary_id: str | None = None
    rating_average: float = 0.0
    rating_count: int = 0
    current_user_rating: int | None = None


class SummaryDetailResponse(BaseModel):
    document: DocumentResponse
    summary: SummaryResponse | None = None
    latest_summary: SummaryResponse | None = None
    preferred_summary: SummaryResponse | None = None
    available_summaries: list[SummaryResponse] = []


class SummaryRatingResponse(BaseModel):
    summary: SummaryResponse
    message: str
    preferred_for_document: bool = False


class SummaryListItem(BaseModel):
    summary_id: str
    document_id: str
    source: str
    language: Literal["vi", "en"]
    summary: str
    method: str
    rating_average: float = 0.0
    rating_count: int = 0
    current_user_rating: int | None = None
    created_at: datetime


class SummaryListResponse(BaseModel):
    items: list[SummaryListItem]
