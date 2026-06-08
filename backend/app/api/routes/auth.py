from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError
import smtplib

from app.core.database import get_database
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import UserRecord
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserPublic,
    VerificationCodeResponse,
    VerifyEmailRequest,
)
from app.services.email_service import (
    build_verification_expiry,
    codes_match,
    generate_verification_code,
    is_code_expired,
    parse_expiry,
    send_verification_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def build_user_public(user: dict, *, is_verified: bool | None = None) -> UserPublic:
    return UserPublic(
        id=str(user["_id"]),
        email=user["email"],
        full_name=user["full_name"],
        is_verified=user.get("is_verified") if is_verified is None else is_verified,
        created_at=user["created_at"],
    )


@router.post("/register", response_model=VerificationCodeResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncIOMotorDatabase = Depends(get_database)) -> VerificationCodeResponse:
    try:
        users = db["users"]
        existing_user = await users.find_one({"email": payload.email})
        if existing_user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

        code = generate_verification_code()
        expires_at = build_verification_expiry()
        hashed_password = hash_password(payload.password)
        delivery_mode = await send_verification_email(payload.email, code)

        user = UserRecord(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hashed_password,
            is_verified=False,
            verification_code={"code": code, "expires_at": expires_at},
        )
        await users.insert_one(user.to_mongo())

        return VerificationCodeResponse(
            message="Verification code sent",
            delivery_mode=delivery_mode,
            expires_at=expires_at,
        )
    except HTTPException:
        raise
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {error}",
        ) from error
    except smtplib.SMTPException as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Email delivery failed: {error}",
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {error}",
        ) from error


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(payload: VerifyEmailRequest, db: AsyncIOMotorDatabase = Depends(get_database)) -> AuthResponse:
    users = db["users"]
    user = await users.find_one({"email": payload.email})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    verification = user.get("verification_code")
    if not verification:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code missing")

    if not codes_match(verification["code"], payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    expires_at = parse_expiry(verification["expires_at"])
    if is_code_expired(expires_at):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired")

    await users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True}, "$unset": {"verification_code": ""}},
    )

    access_token = create_access_token(str(user["_id"]))
    return AuthResponse(
        access_token=access_token,
        user=build_user_public(user, is_verified=True),
    )


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_database)) -> AuthResponse:
    users = db["users"]
    user = await users.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.get("is_verified"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not verified")

    access_token = create_access_token(str(user["_id"]))
    return AuthResponse(
        access_token=access_token,
        user=build_user_public(user),
    )


@router.post("/resend-code", response_model=VerificationCodeResponse)
async def resend_code(payload: MessageResponse, db: AsyncIOMotorDatabase = Depends(get_database)) -> VerificationCodeResponse:
    try:
        users = db["users"]
        email = payload.message.strip()
        user = await users.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        code = generate_verification_code()
        expires_at = build_verification_expiry()
        delivery_mode = await send_verification_email(email, code)
        await users.update_one(
            {"_id": user["_id"]},
            {"$set": {"verification_code": {"code": code, "expires_at": expires_at}, "is_verified": False}},
        )

        return VerificationCodeResponse(
            message="Verification code sent",
            delivery_mode=delivery_mode,
            expires_at=expires_at,
        )
    except HTTPException:
        raise
    except smtplib.SMTPException as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Email delivery failed: {error}",
        ) from error
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {error}",
        ) from error
