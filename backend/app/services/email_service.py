import asyncio
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
import random
import smtplib

from fastapi import HTTPException, status

from app.core.config import get_settings


def generate_verification_code() -> str:
    return f"{random.randint(100000, 999999)}"


def build_verification_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(UTC) + timedelta(minutes=settings.verification_code_ttl_minutes)


async def send_verification_email(email: str, code: str) -> str:
    settings = get_settings()
    if not settings.smtp_username or not settings.smtp_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMTP is not configured",
        )

    def send_email_sync() -> None:
        message = EmailMessage()
        message["Subject"] = "Mã xác thực tài khoản Summarize AI"
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = email
        message.set_content(
            "Chào bạn,\n\n"
            "Cảm ơn bạn đã đăng ký sử dụng Summarize AI.\n"
            f"Mã xác thực (OTP) của bạn là: {code}\n\n"
            f"Mã này sẽ hết hạn sau {settings.verification_code_ttl_minutes} phút."
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_password.replace(" ", ""))
            smtp.send_message(message)

    await asyncio.to_thread(send_email_sync)
    return "smtp-sent"


def normalize_verification_code(value: str) -> str:
    return value.strip()


def codes_match(expected: str, provided: str) -> bool:
    return normalize_verification_code(expected) == normalize_verification_code(provided)


def is_code_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at < datetime.now(UTC)


def parse_expiry(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value
