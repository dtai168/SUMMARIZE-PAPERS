from __future__ import annotations

from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.document import ChatMessageRecord


class ChatHistoryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.chat_messages = db["chat_messages"]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        if self._indexes_ready:
            return

        # TTL 30 days
        await self.chat_messages.create_index(
            [("created_at", 1)],
            expireAfterSeconds=30 * 24 * 60 * 60,
            name="ttl_created_at_30d",
        )
        await self.chat_messages.create_index(
            [("user_id", 1), ("document_id", 1), ("created_at", -1)],
            name="user_document_created_at_desc",
        )

        self._indexes_ready = True

    async def save_message(
        self,
        *,
        user_id: str,
        document_id: str,
        question: str,
        answer: str,
        method: str,
        source: str,
    ) -> dict:
        await self.ensure_indexes()
        record = ChatMessageRecord(
            user_id=user_id,
            document_id=document_id,
            question=question,
            answer=answer,
            method=method,
            source=source,
            created_at=datetime.now(UTC),
        )
        result = await self.chat_messages.insert_one(record.to_mongo())
        return await self.chat_messages.find_one({"_id": result.inserted_id})

    async def list_messages(
        self,
        *,
        user_id: str,
        document_id: str,
        limit: int = 50,
    ) -> list[dict]:
        await self.ensure_indexes()
        items: list[dict] = []
        cursor = (
            self.chat_messages.find({"user_id": user_id, "document_id": document_id})
            .sort([("created_at", -1)])
            .limit(int(limit))
        )
        async for item in cursor:
            items.append(item)

        # Return ascending for UI
        items.reverse()
        return items

    @staticmethod
    def serialize_message(record: dict) -> dict:
        return {
            "id": str(record["_id"]),
            "document_id": record["document_id"],
            "question": record["question"],
            "answer": record["answer"],
            "method": record.get("method") or "",
            "source": record.get("source") or "",
            "created_at": record["created_at"],
        }
