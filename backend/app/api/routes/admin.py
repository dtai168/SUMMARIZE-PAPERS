from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.database import get_database
from app.core.security import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


def _parse_admin_emails(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


async def require_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    settings = get_settings()
    allowlist = _parse_admin_emails(settings.admin_emails)
    email = (current_user.get("email") or "").strip().lower()
    if not allowlist or email not in allowlist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


async def require_super_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    settings = get_settings()
    allowlist = _parse_admin_emails(settings.super_admin_emails)
    email = (current_user.get("email") or "").strip().lower()
    if not allowlist or email not in allowlist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return current_user


async def _build_kpis(db: AsyncIOMotorDatabase) -> dict:
    users_col = db["users"]
    docs_col = db["documents"]
    summaries_col = db["summaries"]

    now = datetime.now(UTC)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_7d = start_today - timedelta(days=6)

    total_users = await users_col.count_documents({})
    verified_users = await users_col.count_documents({"is_verified": True})

    total_documents = await docs_col.count_documents({})
    total_pdf_documents = await docs_col.count_documents({"source_type": "pdf"})
    total_text_documents = await docs_col.count_documents({"source_type": "text"})

    total_summaries = await summaries_col.count_documents({})
    summaries_today = await summaries_col.count_documents({"created_at": {"$gte": start_today}})
    summaries_7d = await summaries_col.count_documents({"created_at": {"$gte": start_7d}})
    rated_summaries = await summaries_col.count_documents({"rating_count": {"$gt": 0}})

    extraction_methods = [
        {"name": row.get("_id") or "unknown", "count": int(row.get("count", 0))}
        async for row in docs_col.aggregate(
            [
                {"$group": {"_id": "$extraction_method", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
        )
    ]

    summary_methods = [
        {"name": row.get("_id") or "unknown", "count": int(row.get("count", 0))}
        async for row in summaries_col.aggregate(
            [
                {"$group": {"_id": "$method", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
        )
    ]

    rating_agg = await summaries_col.aggregate(
        [
            {
                "$group": {
                    "_id": None,
                    "rating_total": {"$sum": {"$ifNull": ["$rating_total", 0]}},
                    "rating_count": {"$sum": {"$ifNull": ["$rating_count", 0]}},
                }
            }
        ]
    ).to_list(length=1)

    rating_total = int(rating_agg[0].get("rating_total", 0)) if rating_agg else 0
    rating_count = int(rating_agg[0].get("rating_count", 0)) if rating_agg else 0
    average_rating = round(rating_total / rating_count, 3) if rating_count > 0 else 0.0

    return {
        "users": {
            "total": total_users,
            "verified": verified_users,
            "verification_rate": _ratio(verified_users, total_users),
        },
        "documents": {
            "total": total_documents,
            "pdf": total_pdf_documents,
            "text": total_text_documents,
            "pdf_ratio": _ratio(total_pdf_documents, total_documents),
            "extraction_methods": extraction_methods,
        },
        "summaries": {
            "total": total_summaries,
            "today": summaries_today,
            "last_7d": summaries_7d,
            "rated": rated_summaries,
            "rated_ratio": _ratio(rated_summaries, total_summaries),
            "average_rating": average_rating,
            "methods": summary_methods,
        },
    }


async def _build_series(db: AsyncIOMotorDatabase, days: int) -> dict:
    start_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    users_col = db["users"]
    docs_col = db["documents"]
    summaries_col = db["summaries"]

    async def _daily_count(col, match_extra: dict | None = None):
        match = {"created_at": {"$gte": start_day}}
        if match_extra:
            match.update(match_extra)
        return [
            {"date": row["_id"], "count": int(row["count"])}
            async for row in col.aggregate(
                [
                    {"$match": match},
                    {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, "count": {"$sum": 1}}},
                    {"$sort": {"_id": 1}},
                ]
            )
        ]

    average_rating = [
        {"date": row["_id"], "average_rating": round(float(row.get("avg_rating", 0.0)), 3)}
        async for row in summaries_col.aggregate(
            [
                {"$match": {"created_at": {"$gte": start_day}, "rating_count": {"$gt": 0}}},
                {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, "avg_rating": {"$avg": "$rating_average"}}},
                {"$sort": {"_id": 1}},
            ]
        )
    ]

    document_sources = [
        {"name": row.get("_id") or "unknown", "count": int(row.get("count", 0))}
        async for row in docs_col.aggregate(
            [
                {"$match": {"created_at": {"$gte": start_day}}},
                {"$group": {"_id": "$source_type", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
        )
    ]

    return {
        "users": await _daily_count(users_col),
        "verified_users": await _daily_count(users_col, {"is_verified": True}),
        "documents": await _daily_count(docs_col),
        "summaries": await _daily_count(summaries_col),
        "average_rating": average_rating,
        "document_sources": document_sources,
    }


async def _build_recent(db: AsyncIOMotorDatabase, limit: int) -> dict:
    users_col = db["users"]
    docs_col = db["documents"]
    summaries_col = db["summaries"]

    users = await users_col.find({}, {"email": 1, "full_name": 1, "is_verified": 1, "created_at": 1}).sort("created_at", -1).limit(limit).to_list(length=limit)
    documents = await docs_col.find({}, {"title": 1, "source_type": 1, "original_filename": 1, "extraction_method": 1, "user_id": 1, "created_at": 1}).sort("created_at", -1).limit(limit).to_list(length=limit)
    summaries = await summaries_col.find({}, {"document_id": 1, "method": 1, "source": 1, "rating_average": 1, "rating_count": 1, "word_count": 1, "created_at": 1}).sort("created_at", -1).limit(limit).to_list(length=limit)

    return {
        "users": [{"id": str(u.get("_id")), "email": u.get("email"), "full_name": u.get("full_name"), "is_verified": u.get("is_verified"), "created_at": u.get("created_at")} for u in users],
        "documents": [{"id": str(d.get("_id")), "title": d.get("title"), "source_type": d.get("source_type"), "original_filename": d.get("original_filename"), "extraction_method": d.get("extraction_method"), "user_id": str(d.get("user_id")) if d.get("user_id") is not None else None, "created_at": d.get("created_at")} for d in documents],
        "summaries": [{"id": str(s.get("_id")), "document_id": str(s.get("document_id")) if s.get("document_id") is not None else None, "method": s.get("method"), "source": s.get("source"), "rating_average": s.get("rating_average"), "rating_count": s.get("rating_count"), "word_count": s.get("word_count"), "created_at": s.get("created_at")} for s in summaries],
    }


async def _build_super_insights(db: AsyncIOMotorDatabase, days: int) -> dict:
    start_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    docs_col = db["documents"]
    summaries_col = db["summaries"]

    top_users_by_documents = [
        {"user_id": str(row.get("_id")) if row.get("_id") is not None else None, "count": int(row.get("count", 0))}
        async for row in docs_col.aggregate(
            [
                {"$match": {"created_at": {"$gte": start_day}}},
                {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
        )
    ]

    low_rated_summaries = [
        {"id": str(row.get("_id")), "document_id": str(row.get("document_id")) if row.get("document_id") is not None else None, "method": row.get("method"), "rating_average": row.get("rating_average"), "rating_count": row.get("rating_count"), "created_at": row.get("created_at")}
        async for row in summaries_col.find({"created_at": {"$gte": start_day}, "rating_count": {"$gte": 3}, "rating_average": {"$lte": 2.5}}, {"document_id": 1, "method": 1, "rating_average": 1, "rating_count": 1, "created_at": 1}).sort("created_at", -1).limit(20)
    ]

    orphan_summaries = await summaries_col.count_documents({"document_id": {"$exists": False}})

    return {
        "top_users_by_documents": top_users_by_documents,
        "low_rated_summaries": low_rated_summaries,
        "anomalies": {"orphan_summaries": orphan_summaries},
    }


@router.get("/me")
async def get_admin_me(_admin_user: dict = Depends(require_admin_user)) -> dict:
    return {"ok": True, "role": "admin"}


@router.get("/kpis")
async def get_admin_kpis(_admin_user: dict = Depends(require_admin_user), db: AsyncIOMotorDatabase = Depends(get_database)) -> dict:
    return await _build_kpis(db)


@router.get("/series")
async def get_admin_series(_admin_user: dict = Depends(require_admin_user), db: AsyncIOMotorDatabase = Depends(get_database), days: int = 30) -> dict:
    if days < 7 or days > 180:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="days must be in [7, 180]")
    return await _build_series(db, days)


@router.get("/recent")
async def get_admin_recent(_admin_user: dict = Depends(require_admin_user), db: AsyncIOMotorDatabase = Depends(get_database), limit: int = 10) -> dict:
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit must be in [1, 50]")
    return await _build_recent(db, limit)


@router.get("/super/me")
async def get_super_admin_me(_admin_user: dict = Depends(require_super_admin_user)) -> dict:
    return {"ok": True, "role": "super_admin"}


@router.get("/super/kpis")
async def get_super_admin_kpis(_admin_user: dict = Depends(require_super_admin_user), db: AsyncIOMotorDatabase = Depends(get_database)) -> dict:
    return await _build_kpis(db)


@router.get("/super/series")
async def get_super_admin_series(_admin_user: dict = Depends(require_super_admin_user), db: AsyncIOMotorDatabase = Depends(get_database), days: int = 30) -> dict:
    if days < 7 or days > 180:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="days must be in [7, 180]")
    return await _build_series(db, days)


@router.get("/super/recent")
async def get_super_admin_recent(_admin_user: dict = Depends(require_super_admin_user), db: AsyncIOMotorDatabase = Depends(get_database), limit: int = 20) -> dict:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit must be in [1, 100]")
    return await _build_recent(db, limit)


@router.get("/super/insights")
async def get_super_admin_insights(_admin_user: dict = Depends(require_super_admin_user), db: AsyncIOMotorDatabase = Depends(get_database), days: int = 30) -> dict:
    if days < 7 or days > 180:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="days must be in [7, 180]")
    return await _build_super_insights(db, days)


@router.get("/super/users/{user_id}")
async def get_super_admin_user_detail(user_id: str, _admin_user: dict = Depends(require_super_admin_user), db: AsyncIOMotorDatabase = Depends(get_database)) -> dict:
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

    user_obj_id = ObjectId(user_id)
    user = await db["users"].find_one({"_id": user_obj_id}, {"email": 1, "full_name": 1, "is_verified": 1, "created_at": 1})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    total_documents = await db["documents"].count_documents({"user_id": user_obj_id})
    total_summaries = await db["summaries"].count_documents({"user_id": user_obj_id})

    return {
        "user": {"id": str(user.get("_id")), "email": user.get("email"), "full_name": user.get("full_name"), "is_verified": user.get("is_verified"), "created_at": user.get("created_at")},
        "stats": {"total_documents": total_documents, "total_summaries": total_summaries},
    }
