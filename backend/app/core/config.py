from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    app_name: str = "Summarize AI API"
    api_prefix: str = "/api"
    frontend_origin: str = "http://localhost:3000"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "summarize_ai"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    verification_code_ttl_minutes: int = 10
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@summarize-ai.local"
    smtp_from_name: str = "Summarize AI"
    summary_model_source: str = "backend/dataops-aisumary-9.ipynb"
    rag_model_source: str = "backend/RAG.ipynb"
    upload_dir: str = "backend/uploads"
    max_upload_size_mb: int = Field(default=20, ge=1, le=100)
    summary_target_words: int = Field(default=500, ge=150, le=2000)
    summary_enable_llm_polish: bool = True
    summary_llm_enable_proofread: bool = False
    summary_debug: bool = False
    debug_summary: bool = False
    summary_llm_model_path: str | None = None
    summary_llm_device_preference: str = "cpu"
    summary_llm_enable_4bit_quantization: bool = True
    summary_llm_max_new_tokens: int = Field(default=768, ge=64, le=4096)
    summary_llm_prompt_max_length: int = Field(default=4096, ge=512, le=8192)
    summary_llm_temperature: float = Field(default=0.45, ge=0.0, le=2.0)
    summary_llm_top_p: float = Field(default=0.92, ge=0.0, le=1.0)
    summary_llm_repetition_penalty: float = Field(default=1.08, ge=0.5, le=3.0)
    summary_llm_typical_p: float = Field(default=0.95, ge=0.0, le=1.0)
    summary_llm_no_repeat_ngram_size: int = Field(default=4, ge=0, le=10)
    summary_target_words_tolerance: float = Field(default=0.08, ge=0.0, le=0.5)
    summary_log_samples: bool = False
    summary_log_sample_chars: int = Field(default=220, ge=0, le=2000)
    summary_force_remove_cjk: bool = True
    summary_style: str = "academic"
    summary_proofread_style: str = "academic"
    summary_proofread_max_new_tokens: int = Field(default=320, ge=64, le=2048)
    summary_proofread_temperature: float = Field(default=0.25, ge=0.0, le=2.0)
    summary_proofread_top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    summary_proofread_repetition_penalty: float = Field(default=1.05, ge=0.5, le=3.0)
    summary_proofread_typical_p: float = Field(default=0.95, ge=0.0, le=1.0)
    summary_proofread_no_repeat_ngram_size: int = Field(default=4, ge=0, le=10)
    summary_proofread_prompt_max_length: int = Field(default=4096, ge=512, le=8192)
    rag_embedding_model_name: str = "bkai-foundation-models/vietnamese-bi-encoder"
    rag_offline: bool = False
    rag_embedding_local_files_only: bool = False
    rag_preload_embeddings_on_startup: bool = False
    rag_debug: bool = False
    rag_embeddings_batch_size: int | None = Field(default=None, ge=1, le=512)
    rag_embeddings_show_progress: bool = False
    rag_fallback_without_embeddings: bool = False
    rag_vectorstore_build_timeout_seconds: int | None = Field(default=None, ge=1, le=3600)
    rag_vectorstore_allow_rebuild: bool = True
    rag_vectorstore_readonly: bool = False
    rag_context_max_chars: int = Field(default=6000, ge=500, le=20000)
    rag_answer_max_chars: int = Field(default=6000, ge=500, le=20000)
    rag_return_context_in_response: bool = False
    rag_return_sources_in_response: bool = False
    rag_force_local_embeddings_path: str | None = None
    rag_embeddings_cache_dir: str | None = None
    rag_hf_home: str | None = None
    rag_hf_hub_offline: bool = False
    rag_transformers_offline: bool = False
    rag_datasets_offline: bool = False
    rag_local_model_dir: str | None = None
    rag_llm_use_api: bool = False
    rag_llm_api_base_url: str | None = None
    rag_llm_api_kind: str = "openai"
    rag_llm_api_model: str | None = None
    rag_llm_api_timeout_seconds: int = Field(default=120, ge=5, le=3600)
    rag_llm_api_max_retries: int = Field(default=1, ge=0, le=10)
    rag_llm_api_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    rag_llm_api_top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    rag_llm_api_repetition_penalty: float = Field(default=1.1, ge=0.5, le=3.0)
    rag_llm_api_max_new_tokens: int = Field(default=512, ge=64, le=4096)
    rag_llm_api_context_prefix: str = ""
    rag_llm_api_system_prompt: str = "Bạn là chuyên gia phân tích bài báo. Chỉ trả lời dựa trên ngữ cảnh cung cấp; nếu thiếu thông tin, nói rõ không tìm thấy trong tài liệu."
    rag_chroma_base_dir: str = "backend/uploads/chroma"
    rag_retriever_k: int = Field(default=4, ge=1, le=20)
    rag_chunk_words: int = Field(default=350, ge=100, le=2000)
    rag_chunk_overlap_words: int = Field(default=60, ge=0, le=500)
    rag_enable_llm_answers: bool = False
    rag_qwen_model_id: str = "Qwen/Qwen2.5-3B-Instruct"
    rag_qwen_model_path: str | None = None
    rag_device_preference: str = "cpu"
    rag_llm_device_preference: str = "cpu"
    rag_enable_4bit_quantization: bool = False
    rag_max_new_tokens: int = Field(default=512, ge=64, le=4096)
    rag_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    rag_top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    rag_repetition_penalty: float = Field(default=1.1, ge=0.5, le=3.0)
    pdf_ocr_language: str = "vie+eng"
    pdf_ocr_dpi: int = Field(default=300, ge=72, le=600)
    pdf_max_pages_to_analyze: int = Field(default=20, ge=1, le=200)
    pdf_min_avg_chars_per_page: int = Field(default=100, ge=1)
    pdf_min_text_page_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    pdf_image_area_ratio_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    pdf_max_garbage_char_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    pdf_preserve_layout: bool = True
    pdf_max_pages: int | None = Field(default=None, ge=1, le=5000)
    admin_emails: str | None = None
    super_admin_emails: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
