from datetime import UTC, datetime

from app.core.config import get_settings
from app.schemas.chat import ChatResponse
from app.services.rag_service import RAGService, _cleanup_sentences, _normalize_answer_output


class ChatService:
    def __init__(self) -> None:
        self.rag_service = RAGService()

    def answer_question(self, *, document_id: str, question: str, locale: str, document_text: str) -> ChatResponse:
        settings = get_settings()
        answer, method = self.rag_service.answer(
            document_id=document_id,
            document_text=document_text,
            question=question,
        )
        answer = _normalize_answer_output(_cleanup_sentences(answer))

        if locale == "en" and method == "reference-rag-retrieval-fallback":
            answer = (
                "The current document was retrieved semantically, but the local answer model is not ready yet. "
                "Below is the most relevant grounded context.\n\n"
                f"{answer}"
            )

        return ChatResponse(
            answer=answer,
            method=method,
            source=settings.rag_model_source,
            created_at=datetime.now(UTC),
        )
