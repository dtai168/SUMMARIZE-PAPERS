from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserPublic"


class VerificationCodeResponse(BaseModel):
    message: str
    delivery_mode: str
    expires_at: datetime


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    is_verified: bool
    created_at: datetime


AuthResponse.model_rebuild()
