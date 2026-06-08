from dataclasses import dataclass

from app.core.config import get_settings
from app.services.summary_reference_summarizer import summarize_pdf_by_textrank


@dataclass
class GeneratedSummary:
    document_id: str
    source: str
    language: str
    summary: str
    method: str
    extractive_summary: str | None = None
    debug: dict | None = None
    guard_reasons: list[str] | None = None
    used_llm: bool | None = None
    used_fallback: bool | None = None


class SummaryService:
    def generate_summary(
        self,
        *,
        document_id: str,
        text: str,
        language: str,
        target_words: int | None = None,
    ) -> GeneratedSummary:
        settings = get_settings()
        use_llm_polish = language == "vi" and settings.summary_enable_llm_polish
        resolved_target_words = target_words or settings.summary_target_words
        result = summarize_pdf_by_textrank(
            raw_text=text,
            target_words=resolved_target_words,
            use_llm_polish=use_llm_polish,
            verbose=False,
        )

        if result.used_llm:
            method = "reference-textrank-qwen"
        elif result.used_fallback and use_llm_polish:
            method = "reference-textrank-fallback"
        else:
            method = "reference-textrank-extractive"

        extractive_summary = result.extractive
        if extractive_summary.strip() == result.final.strip():
            compact_selected = [
                item.get("text", "")
                for item in result.selected[: max(3, min(6, len(result.selected) // 2 or 3))]
                if item.get("text")
            ]
            if compact_selected:
                extractive_summary = " ".join(compact_selected)

        debug = result.debug if settings.debug_summary else None

        return GeneratedSummary(
            document_id=document_id,
            source="D:/summarize_backend/summarize_backend",
            language=language,
            summary=result.final,
            method=method,
            extractive_summary=extractive_summary,
            debug=debug,
            guard_reasons=result.guard_reasons,
            used_llm=result.used_llm,
            used_fallback=result.used_fallback,
        )

