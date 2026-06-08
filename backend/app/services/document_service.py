import hashlib
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.document import DocumentRecord, SummaryRatingRecord, SummaryRecord


class DocumentService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.documents = db["documents"]
        self.summaries = db["summaries"]
        self.summary_ratings = db["summary_ratings"]

    async def create_text_document(self, *, user_id: str, title: str, text: str, language: str) -> dict[str, Any]:
        content_hash = self.build_content_hash(text)
        existing = await self.find_document_by_content_hash(content_hash, source_type="text", user_id=user_id)
        if existing:
            return existing

        record = DocumentRecord(
            user_id=user_id,
            title=title,
            source_type="text",
            language=language,
            extracted_text=text,
            extraction_method="manual-text-input",
            content_hash=content_hash,
        )
        result = await self.documents.insert_one(record.to_mongo())
        return await self.documents.find_one({"_id": result.inserted_id})

    async def create_pdf_document(
        self,
        *,
        user_id: str,
        title: str,
        text: str,
        language: str,
        file_path: str,
        extraction_method: str,
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        content_hash = self.build_content_hash(text)
        existing = await self.find_document_by_content_hash(content_hash, source_type="pdf", user_id=user_id)
        if existing:
            return existing

        record = DocumentRecord(
            user_id=user_id,
            title=title,
            source_type="pdf",
            language=language,
            extracted_text=text,
            file_path=file_path,
            original_filename=original_filename,
            extraction_method=extraction_method,
            content_hash=content_hash,
        )
        result = await self.documents.insert_one(record.to_mongo())
        return await self.documents.find_one({"_id": result.inserted_id})

    async def get_document(self, document_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(document_id):
            return None
        return await self.documents.find_one({"_id": ObjectId(document_id)})

    async def find_document_by_content_hash(self, content_hash: str, *, source_type: str, user_id: str) -> dict[str, Any] | None:
        return await self.documents.find_one(
            {"content_hash": content_hash, "source_type": source_type, "user_id": user_id},
            sort=[("created_at", -1)],
        )

    async def save_summary(self, *, document_id: str, summary: str, method: str, source: str, extractive_summary: str | None = None) -> dict[str, Any]:
        latest = await self.get_latest_summary(document_id)
        if latest and latest.get("summary") == summary and latest.get("method") == method and latest.get("source") == source:
            return latest

        record = SummaryRecord(document_id=document_id, summary=summary, method=method, source=source)
        payload = record.to_mongo()
        if extractive_summary:
            payload["extractive_summary"] = extractive_summary
        result = await self.summaries.insert_one(payload)
        return await self.summaries.find_one({"_id": result.inserted_id})

    async def get_summary(self, summary_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(summary_id):
            return None
        return await self.summaries.find_one({"_id": ObjectId(summary_id)})

    async def get_latest_summary(self, document_id: str) -> dict[str, Any] | None:
        return await self.summaries.find_one({"document_id": document_id}, sort=[("created_at", -1)])

    async def get_preferred_summary(self, document_id: str) -> dict[str, Any] | None:
        return await self.summaries.find_one(
            {"document_id": document_id},
            sort=[("rating_average", -1), ("rating_count", -1), ("created_at", -1)],
        )

    async def get_document_with_latest_summary(self, document_id: str) -> dict[str, Any] | None:
        document = await self.get_document(document_id)
        if not document:
            return None
        document["latest_summary"] = await self.get_latest_summary(document_id)
        document["preferred_summary"] = await self.get_preferred_summary(document_id)
        return document

    async def get_user_rating_for_summary(self, *, summary_id: str, user_id: str) -> int | None:
        rating = await self.summary_ratings.find_one({"summary_id": summary_id, "user_id": user_id})
        if not rating:
            return None
        return int(rating["rating"])

    async def rate_summary(self, *, summary_id: str, document_id: str, user_id: str, rating: int) -> dict[str, Any] | None:
        summary = await self.get_summary(summary_id)
        if not summary:
            return None

        existing = await self.summary_ratings.find_one({"summary_id": summary_id, "user_id": user_id})
        now = datetime.now(UTC)
        if existing:
            previous_rating = int(existing["rating"])
            await self.summary_ratings.update_one(
                {"_id": existing["_id"]},
                {"$set": {"rating": rating, "updated_at": now}},
            )
            rating_delta = rating - previous_rating
            count_delta = 0
        else:
            record = SummaryRatingRecord(
                summary_id=summary_id,
                document_id=document_id,
                user_id=user_id,
                rating=rating,
                created_at=now,
                updated_at=now,
            )
            await self.summary_ratings.insert_one(record.to_mongo())
            rating_delta = rating
            count_delta = 1

        next_total = int(summary.get("rating_total", 0)) + rating_delta
        next_count = int(summary.get("rating_count", 0)) + count_delta
        next_average = next_total / next_count if next_count else 0.0
        await self.summaries.update_one(
            {"_id": summary["_id"]},
            {
                "$set": {
                    "rating_total": next_total,
                    "rating_count": next_count,
                    "rating_average": next_average,
                }
            },
        )
        return await self.get_summary(summary_id)

    async def get_history(self, *, user_id: str) -> list[dict[str, Any]]:
        items = []
        async for item in self.documents.find({"user_id": user_id}).sort("created_at", -1):
            preferred_summary = await self.get_preferred_summary(str(item["_id"]))
            latest_summary = await self.get_latest_summary(str(item["_id"]))
            item["latest_summary"] = latest_summary
            item["preferred_summary"] = preferred_summary
            items.append(item)
        return items

    @staticmethod
    def serialize_summary(summary: dict[str, Any] | None, *, user_rating: int | None = None) -> dict[str, Any] | None:
        if not summary:
            return None
        text = summary.get("summary") or ""
        return {
            "summary_id": str(summary["_id"]),
            "document_id": summary["document_id"],
            "source": summary["source"],
            "language": summary.get("language", "vi"),
            "summary": text,
            "extractive_summary": summary.get("extractive_summary"),
            "word_count": len(text.split()),
            "method": summary["method"],
            "rating_average": float(summary.get("rating_average", 0.0)),
            "rating_count": int(summary.get("rating_count", 0)),
            "current_user_rating": user_rating,
            "created_at": summary["created_at"],
        }

    @staticmethod
    def serialize_document(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(document["_id"]),
            "title": document["title"],
            "source_type": document["source_type"],
            "language": document["language"],
            "created_at": document["created_at"],
            "extraction_method": document.get("extraction_method"),
            "reused_existing": bool(document.get("reused_existing", False)),
        }

    async def attach_user_rating(self, summary: dict[str, Any] | None, *, user_id: str | None) -> dict[str, Any] | None:
        if not summary:
            return None
        user_rating = None
        if user_id:
            user_rating = await self.get_user_rating_for_summary(summary_id=str(summary["_id"]), user_id=user_id)
        return self.serialize_summary(summary, user_rating=user_rating)

    async def get_preferred_summary_payload(self, document_id: str, *, user_id: str | None) -> dict[str, Any] | None:
        summary = await self.get_preferred_summary(document_id)
        return await self.attach_user_rating(summary, user_id=user_id)

    async def get_latest_summary_payload(self, document_id: str, *, user_id: str | None) -> dict[str, Any] | None:
        summary = await self.get_latest_summary(document_id)
        return await self.attach_user_rating(summary, user_id=user_id)

    @staticmethod
    def build_content_hash(text: str) -> str:
        normalized = " ".join(text.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
