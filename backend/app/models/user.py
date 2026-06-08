from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class VerificationCode(BaseModel):
    code: str
    expires_at: datetime


class UserRecord(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    hashed_password: str
    is_verified: bool = False
    verification_code: VerificationCode | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(mode="python")
