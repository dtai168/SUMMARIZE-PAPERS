from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.database import get_database
from app.core.security import get_current_user
from app.schemas.summary import (
    DocumentResponse,
    SummaryCreateTextRequest,
    SummaryDetailResponse,
    SummaryGenerateRequest,
    SummaryHistoryItem,
    SummaryRateRequest,
    SummaryRatingResponse,
    SummaryResponse,
    UploadDocumentResponse,
)
from app.services.document_service import DocumentService
from app.services.summary_reference_config import cfg as reference_summary_cfg
from app.services.summary_reference_pdf_processor import get_pdf_text_smart
from app.services.summary_service import SummaryService

router = APIRouter(prefix="/summary", tags=["summary"])
summary_service = SummaryService()
settings = get_settings()


def build_document_response(document: dict) -> DocumentResponse:
    return DocumentResponse(**DocumentService.serialize_document(document))


def build_summary_response(summary_payload: dict | None) -> SummaryResponse | None:
    if not summary_payload:
        return None
    return SummaryResponse(**summary_payload)




async def build_available_summaries(
    document_service: DocumentService,
    *,
    document_id: str,
    user_id: str | None,
) -> list[SummaryResponse]:
    items: list[SummaryResponse] = []
    async for summary in document_service.summaries.find({"document_id": document_id}).sort(
        [("rating_average", -1), ("rating_count", -1), ("created_at", -1)]
    ):
        payload = await document_service.attach_user_rating(summary, user_id=user_id)
        if payload:
            items.append(SummaryResponse(**payload))
    return items


async def build_summary_result(
    document_service: DocumentService,
    *,
    summary_record: dict,
    user_id: str | None,
) -> SummaryResponse:
    payload = await document_service.attach_user_rating(summary_record, user_id=user_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")
    return SummaryResponse(**payload)


async def get_preferred_summary_or_none(
    document_service: DocumentService,
    *,
    document_id: str,
    user_id: str | None,
) -> SummaryResponse | None:
    payload = await document_service.get_preferred_summary_payload(document_id, user_id=user_id)
    return build_summary_response(payload)


async def get_latest_summary_or_none(
    document_service: DocumentService,
    *,
    document_id: str,
    user_id: str | None,
) -> SummaryResponse | None:
    payload = await document_service.get_latest_summary_payload(document_id, user_id=user_id)
    return build_summary_response(payload)


@router.post("/upload", response_model=UploadDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf_document(
    file: UploadFile = File(...),
    language: str = Form("vi"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> UploadDocumentResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF uploads are supported")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "document.pdf"
    file_path = upload_dir / filename
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file exceeds size limit")

    file_path.write_bytes(content)
    try:
        extracted_text = get_pdf_text_smart(str(file_path), reference_summary_cfg).strip()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error) if str(error) else "Could not extract text from PDF",
        )

    if not extracted_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Could not extract text from PDF")

    document_service = DocumentService(db)
    existing = await document_service.find_document_by_content_hash(
        document_service.build_content_hash(extracted_text),
        source_type="pdf",
        user_id=str(current_user["_id"]),
    )
    document = await document_service.create_pdf_document(
        user_id=str(current_user["_id"]),
        title=Path(filename).stem,
        text=extracted_text,
        language=language if language in {"vi", "en"} else "vi",
        file_path=str(file_path),
        extraction_method="reference-smart-pdf",
        original_filename=filename,
    )
    reused_existing = existing is not None and str(existing["_id"]) == str(document["_id"])
    return UploadDocumentResponse(
        id=str(document["_id"]),
        title=document["title"],
        source_type="pdf",
        language=document["language"],
        created_at=document["created_at"],
        extraction_method=document.get("extraction_method"),
        reused_existing=reused_existing,
    )


@router.post("/text", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_text_document(
    payload: SummaryCreateTextRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> DocumentResponse:
    document_service = DocumentService(db)
    title = payload.title or "Pasted article text"
    existing = await document_service.find_document_by_content_hash(
        document_service.build_content_hash(payload.text),
        source_type="text",
        user_id=str(current_user["_id"]),
    )
    document = await document_service.create_text_document(
        user_id=str(current_user["_id"]),
        title=title,
        text=payload.text,
        language=payload.language,
    )
    reused_existing = existing is not None and str(existing["_id"]) == str(document["_id"])
    return DocumentResponse(
        id=str(document["_id"]),
        title=document["title"],
        source_type=document["source_type"],
        language=document["language"],
        created_at=document["created_at"],
        extraction_method=document.get("extraction_method"),
        reused_existing=reused_existing,
    )


@router.post("/{document_id}/generate", response_model=SummaryResponse)
async def generate_summary(
    document_id: str,
    payload: SummaryGenerateRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> SummaryResponse:
    document_service = DocumentService(db)
    document = await document_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    user_id = str(current_user["_id"])
    if not payload.force_regenerate:
        latest_summary = await document_service.get_latest_summary(document_id)
        if latest_summary:
            return await build_summary_result(document_service, summary_record=latest_summary, user_id=user_id)

    response = summary_service.generate_summary(
        document_id=document_id,
        text=document["extracted_text"],
        language=payload.language,
        target_words=payload.target_words,
    )
    saved = await document_service.save_summary(
        document_id=document_id,
        summary=response.summary,
        method=response.method,
        source=response.source,
        extractive_summary=response.extractive_summary,
    )
    result = await build_summary_result(document_service, summary_record=saved, user_id=user_id)
    if get_settings().debug_summary:
        result.debug = response.debug
    return result


@router.get("/history", response_model=list[SummaryHistoryItem])
async def get_history(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> list[SummaryHistoryItem]:
    document_service = DocumentService(db)
    user_id = str(current_user["_id"])
    items = await document_service.get_history(user_id=user_id)
    history: list[SummaryHistoryItem] = []
    for item in items:
        preferred_summary = item.get("preferred_summary")
        current_user_rating = None
        if preferred_summary and user_id:
            current_user_rating = await document_service.get_user_rating_for_summary(
                summary_id=str(preferred_summary["_id"]),
                user_id=user_id,
            )
        history.append(
            SummaryHistoryItem(
                id=str(item["_id"]),
                title=item["title"],
                source_type=item["source_type"],
                created_at=item["created_at"],
                status="ready" if preferred_summary else "processing",
                has_summary=bool(preferred_summary),
                extraction_method=item.get("extraction_method"),
                summary_created_at=preferred_summary.get("created_at") if preferred_summary else None,
                summary_id=str(preferred_summary["_id"]) if preferred_summary else None,
                rating_average=float(preferred_summary.get("rating_average", 0.0)) if preferred_summary else 0.0,
                rating_count=int(preferred_summary.get("rating_count", 0)) if preferred_summary else 0,
                current_user_rating=current_user_rating,
            )
        )
    return history


@router.get("/{document_id}", response_model=SummaryDetailResponse)
async def get_summary_detail(
    document_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> SummaryDetailResponse:
    document_service = DocumentService(db)
    document = await document_service.get_document_with_latest_summary(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    user_id = str(current_user["_id"])
    preferred_summary = await get_preferred_summary_or_none(document_service, document_id=document_id, user_id=user_id)
    latest_summary = await get_latest_summary_or_none(document_service, document_id=document_id, user_id=user_id)
    available_summaries = await build_available_summaries(document_service, document_id=document_id, user_id=user_id)
    return SummaryDetailResponse(
        document=build_document_response(document),
        summary=preferred_summary,
        latest_summary=latest_summary,
        preferred_summary=preferred_summary,
        available_summaries=available_summaries,
    )


@router.post("/{document_id}/summaries/{summary_id}/rate", response_model=SummaryRatingResponse)
async def rate_summary(
    document_id: str,
    summary_id: str,
    payload: SummaryRateRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> SummaryRatingResponse:
    document_service = DocumentService(db)
    document = await document_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    summary = await document_service.get_summary(summary_id)
    if not summary or summary.get("document_id") != document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")

    user_id = str(current_user["_id"])
    updated_summary = await document_service.rate_summary(
        summary_id=summary_id,
        document_id=document_id,
        user_id=user_id,
        rating=payload.rating,
    )
    if not updated_summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")

    preferred_summary = await document_service.get_preferred_summary(document_id)
    preferred_for_document = bool(preferred_summary and str(preferred_summary["_id"]) == summary_id)
    return SummaryRatingResponse(
        summary=await build_summary_result(document_service, summary_record=updated_summary, user_id=user_id),
        message="Summary rating saved",
        preferred_for_document=preferred_for_document,
    )
