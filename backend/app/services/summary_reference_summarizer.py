from __future__ import annotations

import math
import os
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import logging

import numpy as np

logger = logging.getLogger(__name__)

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

try:
    import torch
except Exception:
    torch = None

try:
    from unsloth import FastLanguageModel
except Exception:
    FastLanguageModel = None

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
except Exception:
    AutoModelForCausalLM = None
    AutoTokenizer = None
    BitsAndBytesConfig = None

from app.core.config import get_settings

SUM_MODEL_NAME = "./qwen_offline"
SUM_MAX_SEQ_LENGTH = 8192
sum_model = None
sum_tokenizer = None
_model_load_attempted = False
_model_backend = None  # "unsloth" | "transformers"

VI_STOPWORDS = {
    "và", "là", "của", "có", "cho", "trong", "được", "với", "các", "những",
    "một", "này", "đó", "khi", "từ", "đến", "trên", "dưới", "về", "theo",
    "tại", "bởi", "do", "nên", "đã", "đang", "sẽ", "rằng", "thì", "mà",
    "như", "hoặc", "nếu", "để", "ra", "vào", "sau", "trước", "giữa",
    "bị", "bằng", "không", "cũng", "nhiều", "ít", "hơn", "nhất", "gồm",
    "qua", "lại", "năm", "ngày", "tháng", "bài", "báo", "nghiên", "cứu",
    "tỷ", "lệ", "kết", "quả",
}

IMPORTANT_TERMS = {
    "mục tiêu", "phương pháp", "kết quả", "kết luận", "tóm tắt", "tổng quan",
    "tóm lại", "nhìn chung", "giai đoạn", "chính sách", "tổ chức",
    "quản lý", "biến động", "lãnh thổ", "phát triển", "thực thi", "chủ quyền",
    "ảnh hưởng", "vai trò", "ý nghĩa", "đánh giá", "tác động", "đặc điểm",
    "đối tượng", "quá trình", "phân tích",
}

SECTION_HEADINGS = [
    "ĐẶT VẤN ĐỀ", "MỞ ĐẦU", "GIỚI THIỆU", "ĐỐI TƯỢNG VÀ PHƯƠNG PHÁP",
    "PHƯƠNG PHÁP NGHIÊN CỨU", "KẾT QUẢ", "BÀN LUẬN", "KẾT LUẬN", "TỔNG KẾT",
]


def _resolve_model_dir() -> str:
    current_dir = os.path.dirname(__file__)
    candidate = os.path.abspath(os.path.join(current_dir, "..", "..", "qwen_offline"))
    if os.path.isdir(candidate):
        return candidate
    return SUM_MODEL_NAME


def _resolved_llm_device() -> str:
    settings = get_settings()
    pref = (settings.summary_llm_device_preference or "cpu").lower()
    if pref == "cpu":
        return "cpu"
    if pref in {"cuda", "gpu", "auto"}:
        return "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
    return "cuda" if torch is not None and torch.cuda.is_available() else "cpu"


def ensure_sum_model() -> bool:
    global sum_model, sum_tokenizer, _model_load_attempted, _model_backend
    if sum_model is not None and sum_tokenizer is not None:
        return True
    if _model_load_attempted:
        return False
    _model_load_attempted = True

    if torch is None:
        return False

    model_dir = _resolve_model_dir()
    if not os.path.isdir(model_dir):
        return False

    device = _resolved_llm_device()

    # Prefer Unsloth when available + CUDA.
    if device == "cuda" and FastLanguageModel is not None:
        try:
            loaded_model, loaded_tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_dir,
                max_seq_length=SUM_MAX_SEQ_LENGTH,
                dtype=None,
                load_in_4bit=True,
            )
            FastLanguageModel.for_inference(loaded_model)
            if loaded_tokenizer.pad_token_id is None:
                loaded_tokenizer.pad_token = loaded_tokenizer.eos_token
            sum_model = loaded_model
            sum_tokenizer = loaded_tokenizer
            _model_backend = "unsloth"
            return True
        except Exception:
            sum_model = None
            sum_tokenizer = None
            _model_backend = None

    # Fallback to transformers (works without Unsloth).
    if AutoModelForCausalLM is None or AutoTokenizer is None:
        return False

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token

        model_kwargs = {}
        if device == "cuda":
            if get_settings().summary_llm_enable_4bit_quantization and BitsAndBytesConfig is not None:
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

        model = AutoModelForCausalLM.from_pretrained(model_dir, **model_kwargs)
        model.eval()
        sum_model = model
        sum_tokenizer = tokenizer
        _model_backend = "transformers"
        return True
    except Exception:
        sum_model = None
        sum_tokenizer = None
        _model_backend = None
        return False


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D")


def _squeeze(text: str) -> str:
    text = _nfc(text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.;:!?%])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def word_count(text: str) -> int:
    return len((text or "").split())


def extract_title(raw_text: str) -> str:
    text = _nfc(raw_text)
    lines = []
    for line in text.splitlines():
        line = _squeeze(line)
        if len(line.split()) >= 8 and not re.search(r"doi|tạp chí|bản quyền", line, re.I):
            lines.append(line)
    return lines[0] if lines else "Tài liệu khoa học/Nghiên cứu"


def remove_abstract_blocks(text: str) -> str:
    text = re.sub(r"(?is)\bTÓM TẮT\b.*?\bTừ kh[oó]a\b.*?(?=\bĐẶT VẤN ĐỀ\b|\bI\.\s*ĐẶT VẤN ĐỀ\b|\b1\.\s*ĐẶT VẤN ĐỀ\b|\bGIỚI THIỆU\b)", " ", text)
    text = re.sub(r"(?is)\bABSTRACT\s*:?.*?\bKeywords?\b.*?(?=\bTÓM TẮT\b|\bĐẶT VẤN ĐỀ\b|\bI\.\s*ĐẶT VẤN ĐỀ\b|\bGIỚI THIỆU\b)", " ", text)
    return text


def _remove_cjk_chars(text: str) -> str:
    if not text:
        return text
    return re.sub(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯\U00020000-\U0002a6df\U0002a700-\U0002ceaf]", " ", text)


def normalize_vi_common_typos(text: str) -> str:
    if not text:
        return text

    # Loại ký tự thay thế/điều khiển thường gặp do OCR
    text = text.replace("", " ").replace("", " ")
    text = text.replace("�", " ")

    # Chuẩn hoá đơn vị tuổi
    text = re.sub(r"\bmonths?\b", "tháng", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmon\b", "tháng", text, flags=re.IGNORECASE)

    # Cụm từ hay sai
    text = re.sub(r"\bbổ\s*dưỡng\b", "bổ sung", text, flags=re.IGNORECASE)

    # Một số lỗi OCR/đánh máy phổ biến trong tên gọi
    text = re.sub(r"\bNhiệt\s*độ\b", "Nhiệt đới", text, flags=re.IGNORECASE)

    # Chuẩn hoá Vitamin D
    text = re.sub(r"\bVitamin\s*D\b", "vitamin D", text)

    # Chuẩn hoá THA viết loạn (THÁ/THÀ/THÉ...) -> THA
    text = re.sub(r"\bTH[\wÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠàáâãèéêìíòóôõùúăđĩũơƯưẠ-Ỵạ-ỵ]{1,3}\b", "THA", text)

    # Chuẩn hoá năm OCR kiểu 2ml 204 / 2m1 204 -> 2024 (heuristic)
    text = re.sub(r"\b2\s*[mM][lL1I]\s*\d\s*0\s*4\b", "2024", text)

    return text


def sanitize_evidence_text(text: str) -> str:
    """Remove table/formula/bullet noise before feeding LLM."""
    if not text:
        return text
    t = _nfc(text)
    t = normalize_vi_common_typos(t)

    # Remove math/formula-like lines and weird symbols from OCR
    t = re.sub(r"[αβγδΔ]+", " ", t)
    t = re.sub(r"\bZ\s*\d*\s*[-–—]*\s*\w+\s*/\s*\d+\b", " ", t)
    t = re.sub(r"\b(p\s*\(\s*1\s*[-–—]?\s*p\s*\))", " ", t, flags=re.IGNORECASE)

    # Drop references to tables/figures and 'Nhận xét'
    t = re.sub(r"(?im)^\s*(bảng|hình|nhận xét)\b.*$", " ", t)

    # Drop list-like bullets within evidence
    t = re.sub(r"(?m)^\s*[-*]+\s+", "", t)
    t = re.sub(r"\s+-\s+", ", ", t)

    # Collapse whitespace
    t = _squeeze(t)
    return t


def _too_listy_or_formulaic(text: str) -> bool:
    if not text:
        return False
    # many bullet markers or formula-ish characters
    if len(re.findall(r"(?m)^\s*[-*]\s+", text)) >= 2:
        return True
    if re.search(r"[αΔ]", text):
        return True
    if re.search(r"\b(p\s*\(\s*1\s*[-–—]?\s*p\s*\))", text, re.IGNORECASE):
        return True
    if re.search(r"(?i)\b(bảng|hình)\s*\d+", text):
        return True
    return False


def _rank_selected(selected: list[dict]) -> list[dict]:
    return sorted(selected, key=lambda item: float(item.get("score", 0.0)), reverse=True)


def _select_evidence_subset(selected: list[dict], max_items: int = 16) -> list[dict]:
    if len(selected) <= max_items:
        return selected
    ranked = _rank_selected(selected)
    keep = ranked[:max_items]
    # keep original order for coherence
    keep_ids = {int(item["idx"]) for item in keep if "idx" in item}
    return [item for item in selected if int(item.get("idx", -1)) in keep_ids]


def clean_pdf_body_text(raw_text: str) -> str:
    settings = get_settings()
    text = _nfc(raw_text).replace("\r", "\n")
    text = normalize_vi_common_typos(text)
    text = remove_abstract_blocks(text)
    text = re.split(r"(?im)^\s*(TÀI LIỆU THAM KHẢO|REFERENCES)\s*$", text)[0]
    if settings.summary_force_remove_cjk and _has_cjk(text):
        text = _remove_cjk_chars(text)

    body_start = None
    for pattern in [r"(?im)^\s*(I\.|1\.)?\s*ĐẶT VẤN ĐỀ\s*$", r"(?im)^\s*(I\.|1\.)?\s*MỞ ĐẦU\s*$", r"(?im)^\s*(I\.|1\.)?\s*GIỚI THIỆU\s*$"]:
        match = re.search(pattern, text)
        if match:
            body_start = match.start()
            break
    if body_start is not None:
        text = text[body_start:]

    noise_patterns = [r"^Tạp chí Khoa học", r"^Tập\s+\d+", r"^Bản quyền", r"^DOI\s*:", r"^https?://", r"^\*?Tác giả liên hệ", r"^Điện thoại\s*:", r"^Email\s*:", r"^Thông tin bài đăng", r"^Ngày nhận bài\s*:", r"^Ngày phản biện\s*:", r"^Ngày duyệt bài\s*:", r"^PGS\.?TS", r"^TS\.", r"^ThS\.", r"^GS\.", r"^BS\.", r"^Viện\s+", r"^Trường Đại học"]
    kept = []
    for line in text.splitlines():
        line = _squeeze(line)
        if not line:
            kept.append("")
            continue
        if re.fullmatch(r"\d{1,3}", line):
            continue
        if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in noise_patterns):
            continue
        letters = len(re.findall(r"[A-Za-zÀ-ỹĐđ]", line))
        digits = len(re.findall(r"\d", line))
        if len(line.split()) <= 4 and digits > letters:
            continue
        kept.append(line)

    text = "\n".join(kept)
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return _squeeze(text)


def protect_abbreviations(text: str) -> str:
    protected = {"cs.": "cs<dot>", "ThS.": "ThS<dot>", "TS.": "TS<dot>", "BS.": "BS<dot>", "PGS.": "PGS<dot>", "GS.": "GS<dot>", "vs.": "vs<dot>", "v.v.": "vv<dot>"}
    for key, value in protected.items():
        text = text.replace(key, value)
    return text


def unprotect_abbreviations(text: str) -> str:
    return text.replace("<dot>", ".")


def split_sentences(text: str) -> list[str]:
    text = protect_abbreviations(_squeeze(text))
    for heading in SECTION_HEADINGS:
        text = re.sub(rf"\b{re.escape(heading)}\b", f". {heading}. ", text, flags=re.IGNORECASE)

    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ỸĐ0-9])", text)
    sentences = []
    for sentence in raw_sentences:
        sentence = unprotect_abbreviations(_squeeze(sentence))
        if not sentence:
            continue
        sentence_words = word_count(sentence)
        if sentence_words < 7 or sentence_words > 90:
            continue
        if re.search(r"(?i)\b(tạp chí|doi|bản quyền|email|điện thoại)\b", sentence):
            continue
        if re.search(r"\bKIẾN NGHỊ\b", sentence, flags=re.IGNORECASE):
            sentence = re.split(r"\bKIẾN NGHỊ\b", sentence, flags=re.IGNORECASE)[0].strip()
            if word_count(sentence) < 7:
                continue
        table_markers = [r"nguyên nhân\s*\( ?% ?\)", r"\bBảng\s+\d+", r"\bBiểu đồ\s+\d+", r"\bHình\s+\d+", r"\(N\s*="]
        if sum(1 for pattern in table_markers if re.search(pattern, sentence, flags=re.IGNORECASE)) >= 2:
            continue
        alpha = len(re.findall(r"[A-Za-zÀ-ỹĐđ]", sentence))
        if alpha < 20:
            continue
        sentences.append(sentence)

    output = []
    seen = set()
    for sentence in sentences:
        key = _strip_accents(sentence.lower())
        key = re.sub(r"[^a-z0-9à-ỹđ]+", " ", key)
        key = " ".join(key.split()[:18])
        if key in seen:
            continue
        seen.add(key)
        output.append(sentence)
    return output


def tokenize_for_rank(sentence: str) -> list[str]:
    normalized = _strip_accents(sentence.lower())
    words = re.findall(r"[a-zA-ZÀ-ỹĐđ]{2,}", normalized)
    return [word for word in words if word not in VI_STOPWORDS and len(word) >= 2]


def build_tfidf_matrix(sentences: list[str], max_terms: int = 1200) -> np.ndarray:
    tokenized = [tokenize_for_rank(sentence) for sentence in sentences]
    document_frequency = Counter()
    term_frequencies = []
    for tokens in tokenized:
        frequency = Counter(tokens)
        term_frequencies.append(frequency)
        document_frequency.update(frequency.keys())

    terms = [term for term, count in document_frequency.most_common(max_terms) if count >= 2 or len(sentences) < 30]
    vocabulary = {term: index for index, term in enumerate(terms)}
    total_sentences = len(sentences)
    matrix = np.zeros((total_sentences, len(vocabulary)), dtype=np.float32)

    for row_index, frequency in enumerate(term_frequencies):
        for term, count in frequency.items():
            column_index = vocabulary.get(term)
            if column_index is None:
                continue
            idf = math.log((1 + total_sentences) / (1 + document_frequency[term])) + 1.0
            matrix[row_index, column_index] = (1.0 + math.log(count)) * idf

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def pagerank_scores(similarity: np.ndarray, damping: float = 0.85, max_iter: int = 100, tol: float = 1e-6) -> np.ndarray:
    total = similarity.shape[0]
    if total == 0:
        return np.array([])
    weights = similarity.copy()
    np.fill_diagonal(weights, 0.0)
    weights[weights < 0.05] = 0.0
    row_sums = weights.sum(axis=1, keepdims=True)
    weights = np.divide(weights, row_sums, out=np.zeros_like(weights), where=row_sums != 0)
    scores = np.ones(total, dtype=np.float32) / total
    base = (1.0 - damping) / total
    for _ in range(max_iter):
        new_scores = base + damping * (weights.T @ scores)
        if np.linalg.norm(new_scores - scores, ord=1) < tol:
            scores = new_scores
            break
        scores = new_scores
    return scores


def section_bonus(sentence: str) -> float:
    sentence_lower = sentence.lower()
    bonus = 1.0
    if any(term in sentence_lower for term in IMPORTANT_TERMS):
        bonus += 0.18
    if re.search(r"(?i)\b(mục tiêu|phương pháp|kết quả|kết luận|tóm tắt|tổng quan)\b", sentence_lower):
        bonus += 0.08
    return bonus


def clean_sentence_for_display(sentence: str) -> str:
    sentence = _squeeze(sentence)
    if get_settings().summary_force_remove_cjk and _has_cjk(sentence):
        sentence = _remove_cjk_chars(sentence)
    sentence = re.split(r"\bKIẾN NGHỊ\b", sentence, flags=re.IGNORECASE)[0]
    sentence = re.sub(r"\s*\(\d+\)\s*", " ", sentence)
    sentence = re.sub(r"\s*\[\d+(?:\s*,\s*\d+)*\]\s*", " ", sentence)
    sentence = re.sub(r"\b(BÀN LUẬN|KẾT LUẬN|KẾT QUẢ|PHƯƠNG PHÁP NGHIÊN CỨU)\b", " ", sentence, flags=re.IGNORECASE)
    sentence = re.sub(r"\s+([,.;:!?%)])", r"\1", sentence)
    sentence = re.sub(r"\.{2,}", ".", sentence)
    sentence = re.sub(r"\s{2,}", " ", sentence)
    return _squeeze(sentence)


def select_sentences_textrank(sentences: list[str], base_scores: np.ndarray, target_words: int = 500, min_words: int = 320, redundancy_threshold: float = 0.72) -> list[dict]:
    if not sentences:
        return []
    matrix = build_tfidf_matrix(sentences)
    similarity = matrix @ matrix.T
    final_scores = np.array([float(base_scores[index]) * section_bonus(sentences[index]) for index in range(len(sentences))], dtype=np.float32)
    order = list(np.argsort(-final_scores))
    selected = []
    selected_ids = []
    total_words = 0

    def is_redundant(index: int, threshold: float = redundancy_threshold) -> bool:
        if not selected_ids:
            return False
        return max(float(similarity[index, selected_index]) for selected_index in selected_ids) > threshold

    def add_index(index: int, *, allow_over: bool = False, threshold: float = redundancy_threshold) -> bool:
        nonlocal total_words
        if index in selected_ids:
            return False
        raw_sentence = sentences[index]
        cleaned_sentence = clean_sentence_for_display(raw_sentence)
        if not cleaned_sentence:
            return False
        sentence_words = word_count(cleaned_sentence)
        upper_words = target_words + max(60, int(target_words * 0.15))
        if (not allow_over) and total_words >= min_words and total_words + sentence_words > upper_words:
            return False
        if total_words + sentence_words > upper_words:
            return False
        if is_redundant(index, threshold=threshold):
            return False
        selected.append({"idx": int(index), "score": float(final_scores[index]), "textrank": float(base_scores[index]), "word_count": sentence_words, "text": raw_sentence, "clean_text": cleaned_sentence})
        selected_ids.append(index)
        total_words += sentence_words
        return True

    def best_index(pattern: str, pool: Optional[range] = None) -> Optional[int]:
        indexes = list(pool) if pool is not None else list(range(len(sentences)))
        candidates = [index for index in indexes if re.search(pattern, sentences[index], flags=re.IGNORECASE)]
        if not candidates:
            return None
        return max(candidates, key=lambda index: final_scores[index])

    total_sentences = len(sentences)
    early_pool = range(0, max(1, min(total_sentences, int(total_sentences * 0.28))))
    seed_patterns = [
        (r"mục tiêu|mục đích|nội dung chính|tóm tắt lại|tổng quan|đặt vấn đề", early_pool),
        (r"phương pháp|cách thức|quá trình|giai đoạn|thời kỳ|tiến trình", None),
        (r"tóm lại|nhìn chung|kết luận|kết quả|cho thấy|đánh giá", None),
        (r"số liệu|tỷ lệ|thống kê|thực thi|quản lý|tác động|ý nghĩa", None),
    ]

    for pattern, pool in seed_patterns:
        index = best_index(pattern, pool)
        if index is not None:
            add_index(index, allow_over=True, threshold=0.88)

    for index in order:
        add_index(index)
        if total_words >= min_words:
            break

    if total_words < min_words:
        for index in order:
            if add_index(index, allow_over=False, threshold=0.92):
                if total_words >= min_words:
                    break

    return sorted(selected, key=lambda item: item["idx"])


def textrank_extract(text: str, target_words: int = 500) -> tuple[list[dict], list[str], np.ndarray]:
    sentences = split_sentences(text)
    if len(sentences) < 5:
        raise RuntimeError(f"Không đủ câu để chạy TextRank: chỉ có {len(sentences)} câu.")
    matrix = build_tfidf_matrix(sentences)
    similarity = matrix @ matrix.T
    scores = pagerank_scores(similarity)
    selected = select_sentences_textrank(sentences=sentences, base_scores=scores, target_words=target_words, min_words=max(120, int(target_words * 0.90)))
    return selected, sentences, scores


def extractive_summary_from_selected(selected: list[dict]) -> str:
    cleaned = []
    seen = set()
    for item in selected:
        sentence = item.get("clean_text") or clean_sentence_for_display(item["text"])
        if not sentence:
            continue
        key = re.sub(r"\W+", " ", _strip_accents(sentence.lower())).strip()[:120]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(sentence)
    if len(cleaned) <= 4:
        return _squeeze(" ".join(cleaned))
    chunks = []
    step = max(2, math.ceil(len(cleaned) / 4))
    for index in range(0, len(cleaned), step):
        chunks.append(" ".join(cleaned[index:index + step]))
    return _squeeze("\n\n".join(chunks))


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯\U00020000-\U0002a6df\U0002a700-\U0002ceaf]", text or ""))


_CJK_BAD_WORDS_IDS = None
_CJK_SCANNED = False


def get_cjk_bad_words_ids():
    global _CJK_BAD_WORDS_IDS, _CJK_SCANNED
    if _CJK_SCANNED:
        return _CJK_BAD_WORDS_IDS
    if sum_tokenizer is None:
        return None
    bad_ids = set()
    vocab = sum_tokenizer.get_vocab()
    for token, token_id in vocab.items():
        if _has_cjk(token):
            bad_ids.add(token_id)
    _CJK_SCANNED = True
    _CJK_BAD_WORDS_IDS = [[token_id] for token_id in sorted(bad_ids)] if bad_ids else None
    return _CJK_BAD_WORDS_IDS


def strip_bad_output(text: str) -> str:
    text = re.sub(r"<\|im_(start|end)\|>", "", text or "")
    text = re.sub(r"(?im)^\s*(system|user|assistant)\s*:?\s*$", "", text)
    text = re.sub(r"(?im)^\s*#{1,6}\s*", "", text)
    text = normalize_vi_common_typos(text)

    # Remove markdown artifacts and heading/list markers not suitable for plain text UI
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^\s*\(?\d+\)?\s*[\).:-]?\s+", "", text)
    text = re.sub(r"(?m)^\s*[-*]\s+", "", text)
    text = re.sub(r"\s*\(\d+\)\s*", " ", text)

    text = _squeeze(text)
    if get_settings().summary_force_remove_cjk and _has_cjk(text):
        text = _squeeze(_remove_cjk_chars(text))
    return text


def sanitize_summary_plaintext(text: str) -> str:
    t = strip_bad_output(text)
    t = re.sub(r"\s+([,.;:!?%])", r"\1", t)
    t = re.sub(r"\.{2,}", ".", t)
    t = re.sub(r"\s{2,}", " ", t)
    return _squeeze(t)


def qwen_proofread_vi(*, draft: str, title: str, selected: list[dict], target_words: int) -> str:
    if not ensure_sum_model() or sum_model is None or sum_tokenizer is None or torch is None:
        raise RuntimeError("Qwen summary model is unavailable in current environment")

    settings = get_settings()
    selected = _select_evidence_subset(selected, max_items=16)
    evidence = "\n".join(
        f"{index + 1}. {sanitize_evidence_text(clean_sentence_for_display(item['text']))}"
        for index, item in enumerate(selected)
    )
    evidence = _squeeze(evidence)
    target_min, target_max = _target_window(target_words)

    system = (
        "Bạn là biên tập viên tiếng Việt, chuyên soát lỗi và chuẩn hóa bản thảo học thuật. "
        "Không thêm dữ kiện mới. Không bịa. Không dùng tiếng Anh/Trung."
    )

    user = f"""Hãy soát và sửa bản thảo sau theo tiêu chí:
- Sửa lỗi chính tả, dấu tiếng Việt, khoảng trắng, từ ghép.
- Chuẩn hóa thuật ngữ chuyên ngành nếu có (giữ nghĩa gốc).
- Thống nhất và GIỮ NGUYÊN tên riêng/địa danh/tổ chức đúng theo BẰNG CHỨNG. Không tự đổi Hải Phòng↔Hải Dương, v.v.
- Loại bỏ hoàn toàn ký tự lạ do OCR (ví dụ: , , α/β/Δ, ký tự thay thế �), loại bỏ bullet/list, loại bỏ dòng kiểu "Bảng/Hình/Nhận xét".
- Không dùng tiếng Anh/Trung. Nếu gặp "months/hypertension" phải chuyển sang tiếng Việt.
- Chuẩn hoá viết tắt THA: chỉ dùng "THA" (không dùng THÁ/THÀ/THÉ...).
- Không thêm thông tin ngoài BẰNG CHỨNG.
- Văn phong: học thuật, mạch lạc, tránh lặp.
- Độ dài: giữ trong [{target_min}, {target_max}] từ (nếu cần, chỉnh câu cho gọn/đủ nhưng không thêm dữ kiện mới).
- Trả về đúng phần văn bản, không giải thích.

Tiêu đề:
{title}

BẰNG CHỨNG:
{evidence}

BẢN THẢO CẦN SỬA:
{draft}

BẢN ĐÃ SỬA:"""

    prompt = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"

    max_prompt_length = settings.summary_proofread_prompt_max_length
    inputs = sum_tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_prompt_length)
    device = _resolved_llm_device()
    if device == "cuda":
        inputs = {k: v.to("cuda") for k, v in inputs.items()}

    kwargs = dict(
        **inputs,
        max_new_tokens=settings.summary_proofread_max_new_tokens,
        do_sample=True,
        temperature=settings.summary_proofread_temperature,
        top_p=settings.summary_proofread_top_p,
        repetition_penalty=settings.summary_proofread_repetition_penalty,
        no_repeat_ngram_size=settings.summary_proofread_no_repeat_ngram_size,
        typical_p=settings.summary_proofread_typical_p,
        pad_token_id=sum_tokenizer.pad_token_id or sum_tokenizer.eos_token_id,
        eos_token_id=sum_tokenizer.eos_token_id,
    )

    bad_words_ids = get_cjk_bad_words_ids()
    if bad_words_ids:
        kwargs["bad_words_ids"] = bad_words_ids

    if settings.summary_debug:
        try:
            n_in = int(inputs["input_ids"].shape[1])
        except Exception:
            n_in = -1
        logger.info(
            "[summary] qwen-pass2 device=%s backend=%s in_tokens=%s max_prompt=%s max_new=%s temp=%.3f top_p=%.3f rep=%.3f typical_p=%.3f ngram=%s",
            device,
            _model_backend,
            n_in,
            settings.summary_proofread_prompt_max_length,
            settings.summary_proofread_max_new_tokens,
            settings.summary_proofread_temperature,
            settings.summary_proofread_top_p,
            settings.summary_proofread_repetition_penalty,
            settings.summary_proofread_typical_p,
            settings.summary_proofread_no_repeat_ngram_size,
        )

    with torch.inference_mode():
        output = sum_model.generate(**kwargs)

    new_ids = output[0][inputs["input_ids"].shape[1]:]
    generated = sum_tokenizer.decode(new_ids, skip_special_tokens=True)
    return strip_bad_output(generated)


def _target_window(target_words: int) -> tuple[int, int]:
    tol = float(get_settings().summary_target_words_tolerance)
    min_ok = max(120, int(target_words * (1.0 - tol)))
    max_ok = int(target_words * (1.0 + tol))
    return min_ok, max_ok


def _maybe_log_sample(label: str, text: str) -> None:
    settings = get_settings()
    if not settings.summary_debug or not settings.summary_log_samples:
        return
    n = int(settings.summary_log_sample_chars)
    if n <= 0:
        return
    sample = (text or "").strip().replace("\n", " ")
    if len(sample) > n:
        sample = sample[:n].rstrip() + "…"
    logger.info("[summary] %s sample=%r", label, sample)


def qwen_polish_textrank(
    title: str,
    selected: list[dict],
    target_words: int = 500,
    *,
    extra_instruction: str | None = None,
    max_new_tokens_override: int | None = None,
) -> str:
    if not ensure_sum_model() or sum_model is None or sum_tokenizer is None or torch is None:
        raise RuntimeError("Qwen summary model is unavailable in current environment")

    selected = _select_evidence_subset(selected, max_items=16)
    evidence = "\n".join(
        f"{index + 1}. {sanitize_evidence_text(clean_sentence_for_display(item['text']))}"
        for index, item in enumerate(selected)
    )
    evidence = _squeeze(evidence)

    system = (
        "Bạn là một biên tập viên học thuật tiếng Việt. "
        "Viết mạch lạc, chính xác, tránh lặp ý và tránh sáo ngữ. "
        "Tuyệt đối không dùng tiếng Anh/Trung, không ký tự lạ, không trình bày dạng danh sách."
    )

    target_min, target_max = _target_window(target_words)

    extra = (extra_instruction or "").strip()
    if extra:
        extra = "\n\nYêu cầu bổ sung:\n" + extra

    user = f"""Bạn sẽ viết một bản tóm tắt học thuật bằng tiếng Việt dựa DUY NHẤT trên các bằng chứng đã cho.

Yêu cầu bắt buộc:
- Độ dài: khoảng {target_words} từ (nằm trong [{target_min}, {target_max}] từ).
- Không bịa: không thêm dữ kiện/số liệu/địa danh/tên riêng ngoài bằng chứng.
- Giữ đúng thực thể: không tự đổi tên trường, địa phương, tổ chức, chức danh; nếu không chắc thì giữ nguyên đúng như bằng chứng.
- Văn phong: học thuật, gọn và rõ; viết văn xuôi; không gạch đầu dòng/đánh số.
- Cấu trúc (viết thành 4-6 đoạn):
  (1) Bối cảnh + mục tiêu nghiên cứu (nếu không nêu rõ, diễn đạt thận trọng "nghiên cứu nhằm khảo sát/đánh giá...").
  (2) Đối tượng và phương pháp (nếu bằng chứng thiếu, ghi "theo mô tả trong tài liệu").
  (3-4) Kết quả/nhận định chính bám sát bằng chứng.
  (5) Kết luận + hàm ý/khuyến nghị (không lặp nguyên văn câu trước).

{extra}

Tiêu đề tài liệu:
{title}

Bằng chứng:
{evidence}

Bản tóm tắt:"""

    # Log nhẹ (không log toàn prompt dài)
    _maybe_log_sample("evidence", evidence)

    prompt = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
    settings = get_settings()
    device = _resolved_llm_device()
    max_prompt_length = settings.summary_llm_prompt_max_length
    max_new_tokens = int(max_new_tokens_override) if max_new_tokens_override else settings.summary_llm_max_new_tokens
    if settings.summary_debug and max_new_tokens_override:
        logger.info("[summary] qwen-pass1 override max_new_tokens=%s", max_new_tokens)
    if max_new_tokens <= 0:
        max_new_tokens = settings.summary_llm_max_new_tokens

    inputs = sum_tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_prompt_length)
    if device == "cuda":
        inputs = {k: v.to("cuda") for k, v in inputs.items()}

    # Các tham số dưới đây thiên về "văn xuôi mượt" hơn là liệt kê.
    # - temperature vừa phải + top_p cao: giảm câu máy móc nhưng vẫn kiểm soát.
    # - repetition_penalty + no_repeat_ngram_size: giảm lặp cụm từ.
    kwargs = dict(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=settings.summary_llm_temperature,
        top_p=settings.summary_llm_top_p,
        repetition_penalty=settings.summary_llm_repetition_penalty,
        no_repeat_ngram_size=settings.summary_llm_no_repeat_ngram_size,
        typical_p=settings.summary_llm_typical_p,
        pad_token_id=sum_tokenizer.pad_token_id or sum_tokenizer.eos_token_id,
        eos_token_id=sum_tokenizer.eos_token_id,
    )

    if settings.summary_debug:
        try:
            n_in = int(inputs["input_ids"].shape[1])
        except Exception:
            n_in = -1
        logger.info(
            "[summary] qwen-pass1 device=%s backend=%s in_tokens=%s max_prompt=%s max_new=%s temp=%.3f top_p=%.3f rep=%.3f typical_p=%.3f ngram=%s",
            device,
            _model_backend,
            n_in,
            settings.summary_llm_prompt_max_length,
            settings.summary_llm_max_new_tokens,
            settings.summary_llm_temperature,
            settings.summary_llm_top_p,
            settings.summary_llm_repetition_penalty,
            settings.summary_llm_typical_p,
            settings.summary_llm_no_repeat_ngram_size,
        )
        started = time.time()
    bad_words_ids = get_cjk_bad_words_ids()
    if bad_words_ids:
        kwargs["bad_words_ids"] = bad_words_ids

    with torch.inference_mode():
        output = sum_model.generate(**kwargs)

    new_ids = output[0][inputs["input_ids"].shape[1]:]
    generated = sum_tokenizer.decode(new_ids, skip_special_tokens=True)
    out = strip_bad_output(generated)

    if settings.summary_debug:
        logger.info("[summary] qwen-pass1 elapsed_ms=%d out_words=%d", int((time.time() - started) * 1000), word_count(out))
        if word_count(out) < max(50, int(target_words * 0.6)):
            logger.info("[summary] qwen-pass1 warning: unusually short output")
        if word_count(out) > int(target_words * 2.0):
            logger.info("[summary] qwen-pass1 warning: unusually long output")

    if settings.summary_force_remove_cjk and _has_cjk(out):
        out = _squeeze(_remove_cjk_chars(out))
    return out


def looks_bad_polish(text: str, selected: list[dict], target_words: int) -> tuple[bool, list[str]]:
    reasons = []
    words = word_count(text)

    min_ok, max_ok = _target_window(target_words)
    if words < min_ok:
        reasons.append(f"quá ngắn ({words}/{target_words} từ)")
    if words > max_ok:
        reasons.append(f"quá dài ({words}/{target_words} từ)")

    # Tránh output kiểu danh sách / đề mục.
    if re.search(r"(?m)^\s*(?:\d+\.|[-*])\s+", text):
        reasons.append("bị biến thành danh sách")
    if re.search(r"(?im)^\s*(tóm tắt|mở đầu|kết luận|phương pháp|kết quả)\s*:\s*", text):
        reasons.append("bị biến thành dạng đề mục")

    if _too_listy_or_formulaic(text):
        reasons.append("lẫn công thức/bảng/hình hoặc bullet")

    # ký tự lạ thường gặp do OCR
    if re.search(r"[αβγδΔ�]", text):
        reasons.append("có ký tự lạ")
    if re.search(r"\b(months?|hypertension)\b", text, flags=re.IGNORECASE):
        reasons.append("lẫn tiếng Anh")
    if re.search(r"\b2\s*[mM][lL1I]\s*\d\s*0\s*4\b", text):
        reasons.append("lẫn năm OCR sai")
    if re.search(r"\bTH[ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỵàáâãèéêìíòóôõùúăđĩũơưạ-ỵ]{1,3}\b", text):
        reasons.append("viết tắt THA bị lỗi OCR")

    # Cảnh báo nếu có ký tự CJK (thường do model trôi sang tiếng Trung).
    if _has_cjk(text):
        reasons.append("lẫn ký tự tiếng Trung")

    return bool(reasons), reasons


def _trim_to_word_range(text: str, *, min_words: int, max_words: int) -> str:
    text = _squeeze(text)
    words = text.split()
    if not words:
        return ""

    # Nếu model bị cắt ở giữa từ (thường do max_new_tokens), bỏ mảnh vụn cuối.
    last = words[-1]
    if len(last) <= 2 and re.fullmatch(r"[A-Za-zÀ-ỹ]+", last):
        words = words[:-1]
        text = " ".join(words).strip()

    if len(words) <= max_words:
        return text

    trimmed = " ".join(words[:max_words]).rstrip(" ,;:.-")
    trimmed = _squeeze(trimmed)
    return trimmed + "." if trimmed and not re.search(r"[.!?]\s*$", trimmed) else trimmed


@dataclass
class TextRankSummaryResult:
    title: str
    body_word_count: int
    sentence_count: int
    selected: list[dict]
    extractive: str
    final: str
    used_llm: bool
    used_fallback: bool
    guard_reasons: list[str]
    elapsed_seconds: float
    debug: dict | None = None


def summarize_pdf_by_textrank(raw_text: str, target_words: int = 500, use_llm_polish: bool = True, verbose: bool = False) -> TextRankSummaryResult:
    started_at = time.time()
    settings = get_settings()
    title = extract_title(raw_text)
    body_text = clean_pdf_body_text(raw_text)

    timings: dict[str, int] = {}

    if settings.summary_debug:
        logger.info(
            "[summary] start target_words=%s use_llm_polish=%s body_words=%s",
            target_words,
            use_llm_polish,
            word_count(body_text),
        )
        _maybe_log_sample("body", body_text)
    clean_done = time.time()
    timings["clean_ms"] = int((clean_done - started_at) * 1000)

    if use_llm_polish:
        # Giữ extractive gọn để tránh fallback quá dài khi Qwen không đạt guard.
        textrank_word_budget = int(target_words * 1.2)
    else:
        textrank_word_budget = target_words

    textrank_started = time.time()
    try:
        selected, sentences, _ = textrank_extract(body_text, target_words=textrank_word_budget)
        extractive = extractive_summary_from_selected(selected)
    except Exception as error:
        sentences = split_sentences(body_text)
        extractive = _squeeze(" ".join(sentences[: min(8, len(sentences))]))
        selected = [{"idx": i, "text": s, "clean_text": clean_sentence_for_display(s)} for i, s in enumerate(sentences[: min(8, len(sentences))])]
        if settings.summary_debug:
            logger.info("[summary] textrank failed: %s", str(error))

    timings["textrank_ms"] = int((time.time() - textrank_started) * 1000)
    if settings.summary_debug:
        logger.info(
            "[summary] textrank sentences=%s selected=%s extractive_words=%s",
            len(sentences),
            len(selected),
            word_count(extractive),
        )
        _maybe_log_sample("extractive", extractive)

    debug: dict[str, object] = {
        "used_llm": False,
        "used_fallback": False,
        "guard_reasons": [],
        "counts": {
            "body_words": word_count(body_text),
            "sentence_count": len(sentences),
            "selected_sentences": len(selected),
            "extractive_words": word_count(extractive),
        },
        "timings_ms": timings,
        "llm": {
            "backend": _model_backend,
            "device": _resolved_llm_device(),
            "enable_4bit": bool(get_settings().summary_llm_enable_4bit_quantization),
        },
    }

    pass1_words = None
    pass2_words = None
    pass1_elapsed_ms = None
    pass2_elapsed_ms = None
    pass1_candidate = None
    pass2_candidate = None
    guard_reasons: list[str] = []

    def _set_debug_llm_state(*, used_llm: bool, used_fallback: bool, reasons: list[str]):
        debug["used_llm"] = used_llm
        debug["used_fallback"] = used_fallback
        debug["guard_reasons"] = reasons
        debug_counts = debug.get("counts", {})
        if isinstance(debug_counts, dict):
            if pass1_words is not None:
                debug_counts["qwen_pass1_words"] = pass1_words
            if pass2_words is not None:
                debug_counts["qwen_pass2_words"] = pass2_words
        debug_timings = debug.get("timings_ms", {})
        if isinstance(debug_timings, dict):
            if pass1_elapsed_ms is not None:
                debug_timings["qwen_pass1_ms"] = pass1_elapsed_ms
            if pass2_elapsed_ms is not None:
                debug_timings["qwen_pass2_ms"] = pass2_elapsed_ms

        if settings.summary_debug:
            logger.info("[summary] llm used_llm=%s used_fallback=%s reasons=%s", used_llm, used_fallback, reasons)

    # Local closure for safe access later
    def _get_debug() -> dict[str, object]:
        return debug

    # attach debug to result at end via attribute (kept out of dataclass schema)
    _debug_payload = debug

    final = extractive
    used_llm = False
    used_fallback = False
    guard_reasons: list[str] = []

    if use_llm_polish:
        try:
            min_ok, max_ok = _target_window(target_words)
            last_candidate = None
            last_reasons: list[str] = []

            # Pass 1: chạy Qwen duy nhất một lần.
            pass1_started = time.time()
            candidate = qwen_polish_textrank(title, selected, target_words=target_words)
            pass1_elapsed_ms = int((time.time() - pass1_started) * 1000)

            candidate = _trim_to_word_range(candidate, min_words=min_ok, max_words=max_ok)
            pass1_candidate = candidate
            pass1_words = word_count(candidate)
            _maybe_log_sample("qwen_pass1", candidate)

            bad, reasons = looks_bad_polish(candidate, selected, target_words)
            last_candidate = candidate
            last_reasons = reasons

            extractive_words = word_count(extractive)
            qwen_words = pass1_words or 0
            extractive_error = abs(extractive_words - target_words)
            qwen_error = abs(qwen_words - target_words)
            qwen_vs_extractive_gap = abs(qwen_words - extractive_words)
            max_gap_vs_extractive = max(40, int(extractive_words * 0.12))

            if isinstance(debug.get("counts"), dict):
                debug["counts"]["extractive_target_error"] = extractive_error
                debug["counts"]["qwen_target_error"] = qwen_error
                debug["counts"]["qwen_vs_extractive_gap"] = qwen_vs_extractive_gap
                debug["counts"]["qwen_vs_extractive_gap_limit"] = max_gap_vs_extractive

            # Ưu tiên Qwen nếu không lệch độ dài quá xa so với TextRank.
            qwen_length_close_to_extractive = qwen_vs_extractive_gap <= max_gap_vs_extractive
            severe_bad = bad and any("lẫn ký tự tiếng Trung" in r for r in reasons)
            if not severe_bad:
                final = candidate
                used_llm = True
                if bad:
                    guard_reasons = reasons
                if not qwen_length_close_to_extractive:
                    guard_reasons = guard_reasons + [
                        f"qwen lệch số từ khá xa so với extractive ({qwen_vs_extractive_gap}>{max_gap_vs_extractive}) nhưng vẫn ưu tiên qwen"
                    ]
            else:
                final = extractive
                used_llm = False
                guard_reasons = reasons + ["đã bỏ output Qwen vì lỗi nội dung nghiêm trọng"]
                used_fallback = True

            # Nếu Qwen pass guard độ dài nhưng lệch target nhiều hơn extractive, vẫn cho phép dùng Qwen
            # để giữ ưu tiên diễn đạt của LLM theo yêu cầu.
            if used_llm and qwen_error > extractive_error and isinstance(debug.get("counts"), dict):
                debug["counts"]["qwen_chosen_despite_higher_target_error"] = True

            # Fallback chỉ khi lỗi nghiêm trọng (CJK/noise nặng), đã xử lý ở nhánh severe_bad.


            # Single-pass mode: skip proofread pass for latency and stability.
            pass2_elapsed_ms = None
            pass2_candidate = None
            pass2_words = None

            # Final cleanup for UI rendering (remove numbering, markdown artifacts)
            final = sanitize_summary_plaintext(final)

            if settings.summary_debug:
                logger.info("[summary] single_pass_cleanup words=%s", word_count(final))

            if not used_llm:
                used_fallback = True
                if not guard_reasons:
                    guard_reasons = last_reasons

            # Nếu chọn Qwen nhưng vẫn có cảnh báo guard thì đánh dấu fallback để UI biết chưa đạt guard.
            if used_llm and guard_reasons:
                used_fallback = True

            _set_debug_llm_state(used_llm=used_llm, used_fallback=used_fallback, reasons=guard_reasons or [])
            debug_llm = debug.get("llm", {})
            if isinstance(debug_llm, dict):
                debug_llm["backend"] = _model_backend
                debug_llm["device"] = _resolved_llm_device()
            if settings.summary_debug:
                logger.info(
                    "[summary] done method=%s final_words=%s",
                    "qwen" if used_llm else "extractive",
                    word_count(final),
                )

            timings["total_ms"] = int((time.time() - started_at) * 1000)
            if isinstance(debug.get("timings_ms"), dict):
                debug["timings_ms"]["total_ms"] = timings["total_ms"]
            if isinstance(debug.get("counts"), dict):
                debug["counts"]["final_words"] = word_count(final)
            if settings.summary_debug:
                logger.info("[summary] timings=%s", debug.get("timings_ms"))
                logger.info("[summary] counts=%s", debug.get("counts"))

        except Exception as error:
            used_fallback = True
            guard_reasons = [str(error)]

    return TextRankSummaryResult(
        title=title,
        body_word_count=word_count(body_text),
        sentence_count=len(sentences),
        selected=selected,
        extractive=extractive,
        final=_squeeze(final),
        used_llm=used_llm,
        used_fallback=used_fallback,
        guard_reasons=guard_reasons,
        elapsed_seconds=time.time() - started_at,
        debug=_debug_payload,
    )
