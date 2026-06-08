from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_database
from app.core.security import get_current_user
from app.schemas.chat import ChatHistoryResponse, ChatMessageResponse, ChatRequest, ChatResponse
from app.services.chat_history_service import ChatHistoryService
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService

router = APIRouter(prefix="/chat", tags=["chat"])
chat_service = ChatService()


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> ChatResponse:
    document_service = DocumentService(db)
    document = await document_service.get_document(payload.document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    response = chat_service.answer_question(
        document_id=payload.document_id,
        question=payload.question,
        locale=payload.locale,
        document_text=document["extracted_text"],
    )

    history_service = ChatHistoryService(db)
    await history_service.save_message(
        user_id=str(current_user["_id"]),
        document_id=payload.document_id,
        question=payload.question,
        answer=response.answer,
        method=response.method,
        source=response.source,
    )

    return response


@router.get("/history", response_model=ChatHistoryResponse)
async def chat_history(
    document_id: str,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> ChatHistoryResponse:
    history_service = ChatHistoryService(db)
    records = await history_service.list_messages(
        user_id=str(current_user["_id"]),
        document_id=document_id,
        limit=limit,
    )
    items = [ChatMessageResponse(**ChatHistoryService.serialize_message(r)) for r in records]
    return ChatHistoryResponse(items=items, document_id=document_id, limit=int(limit), total_returned=len(items))


@router.get("/health", include_in_schema=False)
async def chat_health() -> dict:
    return {"status": "ok"}
