from __future__ import annotations

import hashlib
import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import torch
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)


def _apply_hf_offline_env(settings) -> None:
    # Optional: enforce offline behavior for HuggingFace stack
    if settings.rag_hf_home:
        os.environ.setdefault("HF_HOME", settings.rag_hf_home)
    if settings.rag_embeddings_cache_dir:
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", settings.rag_embeddings_cache_dir)
        os.environ.setdefault("TRANSFORMERS_CACHE", settings.rag_embeddings_cache_dir)

    if settings.rag_hf_hub_offline or settings.rag_offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
    if settings.rag_transformers_offline or settings.rag_offline:
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    if settings.rag_datasets_offline or settings.rag_offline:
        os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _norm_path(p: str) -> str:
    return str(Path(p).resolve())


def _exists_dir(p: str | None) -> bool:
    return bool(p) and Path(p).exists() and Path(p).is_dir()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def _safe_ms(seconds: float) -> int:
    return int(seconds * 1000)


def _maybe_log(settings, msg: str, *args) -> None:
    if settings.rag_debug:
        logger.info(msg, *args)


def _now() -> float:
    return time.time()


def _secs_since(start: float) -> float:
    return time.time() - start


def _resolve_embedding_model(settings) -> str:
    if _exists_dir(settings.rag_force_local_embeddings_path):
        return _norm_path(settings.rag_force_local_embeddings_path)
    if _exists_dir(settings.rag_embedding_model_name):
        return _norm_path(settings.rag_embedding_model_name)
    return settings.rag_embedding_model_name


def _embedding_model_kwargs(settings, device: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"device": device}
    if settings.rag_embedding_local_files_only or settings.rag_offline:
        kwargs["local_files_only"] = True
    if settings.rag_embeddings_cache_dir:
        kwargs["cache_folder"] = settings.rag_embeddings_cache_dir
    return kwargs


def _embedding_encode_kwargs(settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"normalize_embeddings": True}
    if settings.rag_embeddings_batch_size:
        kwargs["batch_size"] = settings.rag_embeddings_batch_size
    return kwargs


def _context_prompt(system_prompt: str, context: str, question: str) -> str:
    return (
        f"{system_prompt}\n\n"
        "Bằng chứng đã chọn từ tài liệu:\n"
        f"{context}\n\n"
        "Câu hỏi:\n"
        f"{question}\n\n"
        "Yêu cầu trả lời:\n"
        "- CHỈ được viết lại từ phần Bằng chứng ở trên, không thêm ý mới.\n"
        "- Câu đầu tiên trả lời trực tiếp câu hỏi.\n"
        "- Không dùng tiếng Trung hoặc thuật ngữ lai Anh-Việt.\n"
        "- Không đề xuất đọc thêm, nghiên cứu thêm, hoặc nguồn ngoài tài liệu.\n"
        "- Nếu bằng chứng không đủ, trả đúng một câu: 'Không tìm thấy trong tài liệu.'.\n"
        "- Trả lời ngắn gọn, 1 đoạn, tối đa 5 câu, không lặp ý.\n\n"
        "Trả lời:"
    )


def _wrap_sources(docs: list[Document]) -> list[dict[str, Any]]:
    out = []
    for doc in docs:
        md = dict(doc.metadata or {})
        out.append({"metadata": md, "text": doc.page_content})
    return out


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sleep_backoff(attempt: int) -> None:
    time.sleep(min(0.25 * (2**attempt), 2.0))


def _http_post_json(url: str, payload: dict, timeout: int) -> dict:
    import json
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def _call_llm_api_openai(settings, prompt: str) -> str:
    base = settings.rag_llm_api_base_url
    model = settings.rag_llm_api_model
    if not base or not model:
        raise RuntimeError("rag_llm_api_base_url/model not configured")
    url = base.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": settings.rag_llm_api_system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": settings.rag_llm_api_temperature,
        "top_p": settings.rag_llm_api_top_p,
        "max_tokens": settings.rag_llm_api_max_new_tokens,
        "presence_penalty": 0,
        "frequency_penalty": max(0.0, float(settings.rag_llm_api_repetition_penalty) - 1.0),
    }

    last_err = None
    for attempt in range(settings.rag_llm_api_max_retries + 1):
        try:
            data = _http_post_json(url, payload, timeout=settings.rag_llm_api_timeout_seconds)
            return (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        except Exception as e:
            last_err = e
            _sleep_backoff(attempt)

    raise RuntimeError(f"LLM API call failed: {last_err}")


def _call_llm_api_ollama(settings, prompt: str) -> str:
    base = settings.rag_llm_api_base_url
    model = settings.rag_llm_api_model
    if not base or not model:
        raise RuntimeError("rag_llm_api_base_url/model not configured")
    url = base.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": settings.rag_llm_api_system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": settings.rag_llm_api_temperature,
            "top_p": settings.rag_llm_api_top_p,
            "repeat_penalty": settings.rag_llm_api_repetition_penalty,
            "num_predict": settings.rag_llm_api_max_new_tokens,
        },
    }

    last_err = None
    for attempt in range(settings.rag_llm_api_max_retries + 1):
        try:
            data = _http_post_json(url, payload, timeout=settings.rag_llm_api_timeout_seconds)
            msg = data.get("message") or {}
            return msg.get("content", "") or ""
        except Exception as e:
            last_err = e
            _sleep_backoff(attempt)

    raise RuntimeError(f"LLM API call failed: {last_err}")


def _call_llm_api(settings, prompt: str) -> str:
    kind = (settings.rag_llm_api_kind or "openai").lower()
    if kind == "ollama":
        return _call_llm_api_ollama(settings, prompt)
    return _call_llm_api_openai(settings, prompt)


def _should_use_llm_api(settings) -> bool:
    return bool(settings.rag_llm_use_api)


def _to_grounded_answer(answer: str) -> str:
    return (answer or "").strip()


def _reduce_context(settings, context: str) -> str:
    return _truncate(context, settings.rag_context_max_chars)


def _reduce_answer(settings, answer: str) -> str:
    return _truncate(answer, settings.rag_answer_max_chars)


def _extract_evidence_context(question: str, context: str, max_sentences: int = 5) -> str:
    import re

    text = (context or "").strip()
    if not text:
        return ""

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return ""

    q_terms = [w for w in re.findall(r"\w+", (question or "").lower()) if len(w) >= 3]

    scored: list[tuple[int, int, str]] = []
    for idx, s in enumerate(sentences):
        low = s.lower()
        term_hits = sum(1 for t in q_terms if t in low)
        medical_hits = sum(1 for t in ["huyết áp", "tăng huyết áp", "triệu chứng", "nguyên nhân", "điều trị", "biến chứng"] if t in low)
        length_penalty = 1 if len(s.split()) > 70 else 0
        score = term_hits * 3 + medical_hits - length_penalty
        scored.append((score, idx, s))

    scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    picked = sorted(scored[:max_sentences], key=lambda x: x[1])
    evidence = " ".join(s for _, _, s in picked).strip()
    return evidence or ""


def _expand_medical_query(question: str) -> str:
    q = (question or "").strip()
    if not q:
        return q

    lower = q.lower()
    expansions: list[str] = []
    if "tha" in lower:
        expansions.append("tăng huyết áp")
    if "tăng áp" in lower:
        expansions.append("tăng huyết áp")
    if "huyết áp" in lower:
        expansions.append("huyết áp động mạch")

    if not expansions:
        return q

    merged = [q]
    seen = {q.lower()}
    for item in expansions:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return " | ".join(merged)


def _prompt_template_text() -> str:
    return (
        "Bạn là trợ lý RAG tiếng Việt cho tài liệu y khoa.\n"
        "Quy tắc bắt buộc:\n"
        "1) Chỉ dùng thông tin có trong phần Ngữ cảnh.\n"
        "2) Không thêm dữ kiện không có trong ngữ cảnh.\n"
        "3) Không dùng tiếng Trung hoặc thuật ngữ lai Anh-Việt.\n"
        "4) Không gợi ý nguồn/sách/website hoặc nghiên cứu thêm ngoài ngữ cảnh.\n"
        "5) Không tự thêm mục điều trị/liều dùng/phản ứng phụ nếu ngữ cảnh không có.\n"
        "6) Nếu không đủ thông tin thì trả đúng: 'Không tìm thấy trong tài liệu.'.\n"
        "7) Trả lời ngắn gọn, 1 đoạn, tối đa 6 câu, không lặp ý.\n\n"
        "Ngữ cảnh:\n{context}\n\n"
        "Câu hỏi:\n{question}\n\n"
        "Trả lời:"
    )


def _prefer_qwen_api(settings) -> bool:
    return settings.rag_llm_use_api and bool(settings.rag_llm_api_base_url) and bool(settings.rag_llm_api_model)


def _is_offline(settings) -> bool:
    return bool(settings.rag_offline)


def _missing_local_embeddings(settings) -> bool:
    name = _resolve_embedding_model(settings)
    if Path(name).is_dir():
        return False
    return settings.rag_offline and ("/" in name or "\\" in name) and not Path(name).exists()


def _maybe_raise_missing_embeddings(settings) -> None:
    if _missing_local_embeddings(settings):
        raise FileNotFoundError(
            f"Embedding model path not found for offline mode: {settings.rag_embedding_model_name}. "
            "Download it locally and set RAG_FORCE_LOCAL_EMBEDDINGS_PATH or RAG_EMBEDDING_MODEL_NAME to that folder."
        )


def _prompt_template_from_settings(settings) -> str:
    return settings.rag_llm_api_context_prefix or _prompt_template_text()


def _contains_english_or_cjk(text: str) -> bool:
    import re

    if re.search(r"[一-鿿]", text or ""):
        return True
    return False


def _postprocess_answer(settings, answer: str, *, question: str = "", context: str = "") -> str:
    import re

    text = (answer or "").strip()
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?i)^trả lời\s*:\s*", "", text).strip()
    text = re.split(r"(?i)\bcâu hỏi\s*:", text, maxsplit=1)[0].strip()

    if not text:
        return ""

    text = re.sub(r"\bMạcs\b", "Mạc", text)
    text = re.sub(r"\bMàn\b", "Mạc", text)

    # remove non-Vietnamese artifacts commonly hallucinated in this flow
    text = re.sub(r"[一-鿿]+", "", text)

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    filtered: list[str] = []
    seen_norm: set[str] = set()

    banned_fragments = [
        "tham khảo thêm",
        "nguồn khác",
        "website",
        "chúc bạn",
        "nghiên cứu sâu rộng hơn",
        "để hiểu rõ hơn",
        "nếu cần thêm thông tin",
        "liều lượng thích hợp",
        "phản ứng phụ",
    ]

    for s in sentences:
        low = s.lower()
        if any(k in low for k in banned_fragments):
            continue

        norm = re.sub(r"[^\wÀ-ỹ]+", "", low)
        if norm in seen_norm:
            continue

        years = re.findall(r"\b20\d{2}\b", s)
        if years and any(y not in context for y in years):
            continue

        seen_norm.add(norm)
        filtered.append(s)
        if len(filtered) >= 6:
            break

    return " ".join(filtered).strip() or text.strip()[:1200]


def _normalize_answer_output(answer: str) -> str:
    import re

    text = (answer or "").strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _cleanup_sentences(answer: str) -> str:
    import re

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", (answer or "").strip()) if s.strip()]
    cleaned: list[str] = []
    seen: set[str] = set()
    for s in sentences:
        key = re.sub(r"[^\wÀ-ỹ]+", "", s.lower())
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(s)
    return " ".join(cleaned).strip() or (answer or "").strip()


def _normalize_answer_output(answer: str) -> str:
    import re

    text = (answer or "").strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _cleanup_sentences(answer: str) -> str:
    import re

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", (answer or "").strip()) if s.strip()]
    cleaned: list[str] = []
    seen: set[str] = set()
    for s in sentences:
        key = re.sub(r"[^\wÀ-ỹ]+", "", s.lower())
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(s)
    return " ".join(cleaned).strip() or (answer or "").strip()

try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

from app.core.config import get_settings


class RAGService:
    def __init__(self) -> None:
        self.settings = get_settings()
        _apply_hf_offline_env(self.settings)

    @lru_cache(maxsize=1)
    def get_embeddings(self) -> HuggingFaceEmbeddings:
        _maybe_raise_missing_embeddings(self.settings)
        started = _now()
        device = self._embedding_device()
        model_name = _resolve_embedding_model(self.settings)
        emb = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=_embedding_model_kwargs(self.settings, device),
            encode_kwargs=_embedding_encode_kwargs(self.settings),
            show_progress=bool(self.settings.rag_embeddings_show_progress),
        )
        _maybe_log(self.settings, "[rag] embeddings ready model=%s device=%s elapsed_ms=%s", model_name, device, _safe_ms(_secs_since(started)))
        return emb

    def preload(self) -> None:
        if not self.settings.rag_preload_embeddings_on_startup:
            return
        try:
            self.get_embeddings()
        except Exception as e:
            _maybe_log(self.settings, "[rag] preload embeddings failed: %s", e)
            if not self.settings.rag_fallback_without_embeddings:
                raise

    @staticmethod
    def prompt_system(settings) -> str:
        return settings.rag_llm_api_system_prompt

    def answer(self, *, document_id: str, document_text: str, question: str) -> tuple[str, str]:
        t0 = _now()
        vectorstore = self.get_or_create_vectorstore(document_id=document_id, document_text=document_text)
        t1 = _now()
        retriever = vectorstore.as_retriever(search_kwargs={"k": self.settings.rag_retriever_k})
        documents = retriever.invoke(question)
        documents = self._expand_retrieved_docs(document_text=document_text, docs=documents, neighbor_window=2)
        t2 = _now()
        context = self.format_docs(documents)
        context = _reduce_context(self.settings, context)
        evidence_context = _extract_evidence_context(question=question, context=context, max_sentences=5)

        _maybe_log(
            self.settings,
            "[rag] retrieve k=%s docs=%s build_ms=%s retrieve_ms=%s context_chars=%s evidence_chars=%s",
            self.settings.rag_retriever_k,
            len(documents),
            _safe_ms(t1 - t0),
            _safe_ms(t2 - t1),
            len(context),
            len(evidence_context),
        )

        if not evidence_context.strip():
            return (
                "Tài liệu hiện tại không cung cấp thông tin về vấn đề này.",
                "reference-rag-empty-context",
            )

        # Prefer API-based LLM (local server) when configured.
        if _prefer_qwen_api(self.settings):
            prompt = _context_prompt(self.settings.rag_llm_api_system_prompt, evidence_context, question)
            llm_started = _now()
            raw_answer = _call_llm_api(self.settings, prompt)
            _maybe_log(self.settings, "[rag] llm_api elapsed_ms=%s", _safe_ms(_secs_since(llm_started)))
            raw_answer = _reduce_answer(self.settings, _to_grounded_answer(raw_answer))
            answer = _postprocess_answer(self.settings, raw_answer, question=question, context=evidence_context)
            if not answer:
                answer = _cleanup_sentences(_normalize_answer_output(raw_answer))
            return answer or self._fallback_answer(context=context, question=question)[0], "reference-rag-qwen-api"

        llm_chain = self.get_llm_chain()
        if llm_chain is None:
            return self._fallback_answer(context=context, question=question)

        llm_started = _now()
        raw_answer = llm_chain.invoke({"context": evidence_context, "question": question}).strip()
        _maybe_log(self.settings, "[rag] llm_local elapsed_ms=%s", _safe_ms(_secs_since(llm_started)))
        if not raw_answer:
            return self._fallback_answer(context=evidence_context, question=question)
        raw_answer = _reduce_answer(self.settings, raw_answer)
        answer = _postprocess_answer(self.settings, raw_answer, question=question, context=evidence_context)
        if not answer:
            answer = _cleanup_sentences(_normalize_answer_output(raw_answer))
        return answer or self._fallback_answer(context=context, question=question)[0], "reference-rag-qwen"

    @lru_cache(maxsize=1)
    def get_llm_chain(self):
        if not self.settings.rag_enable_llm_answers:
            return None

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, pipeline
            from langchain_huggingface import HuggingFacePipeline
        except Exception:
            return None

        model_path = self._resolve_qwen_model_path()
        model_id = model_path or self.settings.rag_qwen_model_id
        if not model_id:
            return None

        try:
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            if tokenizer.pad_token_id is None:
                tokenizer.pad_token = tokenizer.eos_token

            model_kwargs: dict[str, Any] = {}
            use_cuda = torch.cuda.is_available() and self._llm_device() != "cpu"

            if use_cuda:
                if self.settings.rag_enable_4bit_quantization:
                    model_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.float16,
                    )
                    model_kwargs["device_map"] = "auto"
                else:
                    model_kwargs["torch_dtype"] = torch.float16
                    model_kwargs["device_map"] = "auto"
            else:
                model_kwargs["device_map"] = None

            model = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)
            generator = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=self.settings.rag_max_new_tokens,
                temperature=self.settings.rag_temperature,
                top_p=self.settings.rag_top_p,
                repetition_penalty=self.settings.rag_repetition_penalty,
                no_repeat_ngram_size=4,
                do_sample=False,
                return_full_text=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
            llm = HuggingFacePipeline(pipeline=generator)
            prompt = PromptTemplate.from_template(_prompt_template_from_settings(self.settings))
            return prompt | llm | StrOutputParser()
        except Exception:
            return None

    def get_or_create_vectorstore(self, *, document_id: str, document_text: str) -> Chroma:
        persist_directory = self._vectorstore_dir(document_id)
        fingerprint_path = persist_directory / ".fingerprint"
        current_fingerprint = self._fingerprint(document_text)
        embeddings = self.get_embeddings()

        if persist_directory.exists() and fingerprint_path.exists():
            saved_fingerprint = fingerprint_path.read_text(encoding="utf-8").strip()
            if saved_fingerprint == current_fingerprint:
                _maybe_log(self.settings, "[rag] vectorstore reuse doc=%s", document_id)
                return Chroma(
                    persist_directory=str(persist_directory),
                    embedding_function=embeddings,
                )

        if self.settings.rag_vectorstore_readonly:
            raise RuntimeError("Vectorstore missing/outdated and rag_vectorstore_readonly=true")

        if persist_directory.exists() and self.settings.rag_vectorstore_allow_rebuild:
            for child in persist_directory.iterdir():
                if child.is_file():
                    child.unlink()
                else:
                    import shutil

                    shutil.rmtree(child)
        else:
            persist_directory.mkdir(parents=True, exist_ok=True)

        documents = self.build_documents(document_id=document_id, document_text=document_text)
        _maybe_log(self.settings, "[rag] building vectorstore doc=%s chunks=%s", document_id, len(documents))
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=str(persist_directory),
        )
        fingerprint_path.write_text(current_fingerprint, encoding="utf-8")
        return vectorstore

    def build_documents(self, *, document_id: str, document_text: str) -> list[Document]:
        chunks = self.chunk_document(document_text)
        return [
            Document(
                page_content=chunk,
                metadata={
                    "document_id": document_id,
                    "chunk_index": index,
                    "zone": "body",
                    "breadcrumbs": f"chunk-{index + 1}",
                },
            )
            for index, chunk in enumerate(chunks)
        ]

    def chunk_document(self, document_text: str) -> list[str]:
        paragraphs = [paragraph.strip() for paragraph in document_text.split("\n\n") if paragraph.strip()]
        if not paragraphs:
            return [document_text.strip()] if document_text.strip() else []

        chunks: list[str] = []
        buffer: list[str] = []
        buffer_words = 0
        chunk_size = self.settings.rag_chunk_words
        chunk_overlap = self.settings.rag_chunk_overlap_words

        for paragraph in paragraphs:
            words = paragraph.split()
            word_count = len(words)
            if word_count >= chunk_size:
                if buffer:
                    chunks.append("\n\n".join(buffer).strip())
                    buffer = []
                    buffer_words = 0
                start = 0
                while start < word_count:
                    end = min(start + chunk_size, word_count)
                    chunk = " ".join(words[start:end]).strip()
                    if chunk:
                        chunks.append(chunk)
                    if end >= word_count:
                        break
                    start = max(end - chunk_overlap, start + 1)
                continue

            if buffer_words + word_count > chunk_size and buffer:
                chunks.append("\n\n".join(buffer).strip())
                if chunk_overlap > 0:
                    overlap_words = " ".join("\n\n".join(buffer).split()[-chunk_overlap:]).strip()
                    buffer = [overlap_words] if overlap_words else []
                    buffer_words = len(overlap_words.split()) if overlap_words else 0
                else:
                    buffer = []
                    buffer_words = 0

            buffer.append(paragraph)
            buffer_words += word_count

        if buffer:
            chunks.append("\n\n".join(buffer).strip())

        return [chunk for chunk in chunks if chunk]

    def _expand_retrieved_docs(self, *, document_text: str, docs: list[Document], neighbor_window: int = 1) -> list[Document]:
        if not docs:
            return docs

        all_chunks = self.chunk_document(document_text)
        if not all_chunks:
            return docs

        selected_indexes: set[int] = set()
        for doc in docs:
            md = doc.metadata or {}
            idx = md.get("chunk_index")
            if not isinstance(idx, int):
                continue
            for i in range(max(0, idx - neighbor_window), min(len(all_chunks), idx + neighbor_window + 1)):
                selected_indexes.add(i)

        # Nếu metadata thiếu thì giữ nguyên docs retrieve ban đầu
        if not selected_indexes:
            return docs

        expanded: list[Document] = []
        for idx in sorted(selected_indexes):
            expanded.append(
                Document(
                    page_content=all_chunks[idx],
                    metadata={
                        "chunk_index": idx,
                        "zone": "body",
                        "breadcrumbs": f"chunk-{idx + 1}",
                    },
                )
            )
        return expanded

    @staticmethod
    def format_docs(docs: list[Document]) -> str:
        return "\n\n---\n\n".join(doc.page_content for doc in docs)

    def _fallback_answer(self, *, context: str, question: str) -> tuple[str, str]:
        answer = (
            "Tài liệu hiện tại đã được truy xuất theo ngữ nghĩa nhưng mô hình trả lời cục bộ chưa sẵn sàng. "
            "Dưới đây là ngữ cảnh phù hợp nhất để bạn tham chiếu.\n\n"
            f"Ngữ cảnh:\n{context[:2200]}\n\n"
            f"Câu hỏi: {question}"
        )
        return answer, "reference-rag-retrieval-fallback"

    def _vectorstore_dir(self, document_id: str) -> Path:
        base_dir = Path(self.settings.rag_chroma_base_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / document_id

    @staticmethod
    def _fingerprint(document_text: str) -> str:
        return hashlib.sha256(document_text.encode("utf-8")).hexdigest()

    def _embedding_device(self) -> str:
        preference = self.settings.rag_device_preference
        if preference == "cpu":
            return "cpu"
        if preference == "cuda" and torch.cuda.is_available():
            return "cuda"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _llm_device(self) -> str:
        preference = self.settings.rag_llm_device_preference
        if preference == "cpu":
            return "cpu"
        if preference == "cuda" and torch.cuda.is_available():
            return "cuda"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _resolve_qwen_model_path(self) -> str | None:
        configured = self.settings.rag_qwen_model_path
        if configured and Path(configured).exists():
            return configured

        project_model = Path(__file__).resolve().parents[2] / "qwen_offline"
        if project_model.exists():
            return str(project_model)
        return None

    @staticmethod
    def _prompt_template() -> str:
        return """<|im_start|>system
Bạn là một chuyên gia phân tích và tóm tắt tài liệu. Nhiệm vụ của bạn là đọc các đoạn "Ngữ cảnh" được trích xuất từ tài liệu và thực hiện yêu cầu của người dùng.
Quy tắc tối thượng:
1. Chỉ dựa vào thông tin có trong phần Ngữ cảnh.
2. Trình bày khoa học, rõ ràng.
3. Tuyệt đối không bịa đặt thêm thông tin. Nếu ngữ cảnh không đủ, hãy nói rõ: "Tài liệu hiện tại không cung cấp thông tin về vấn đề này."<|im_end|>
<|im_start|>user
Ngữ cảnh trích xuất từ tài liệu:
{context}

Yêu cầu/Câu hỏi của tôi: {question}<|im_end|>
<|im_start|>assistant
"""
