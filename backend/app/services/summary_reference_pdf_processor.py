import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

import fitz
import pdfplumber
import pytesseract
from pdf2image import convert_from_path


def _ensure_tesseract_command() -> None:
    if getattr(pytesseract.pytesseract, "tesseract_cmd", None) and os.path.exists(pytesseract.pytesseract.tesseract_cmd):
        return

    env_cmd = os.getenv("TESSERACT_CMD")
    if env_cmd and os.path.exists(env_cmd):
        pytesseract.pytesseract.tesseract_cmd = env_cmd
        return

    default_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(default_cmd):
        pytesseract.pytesseract.tesseract_cmd = default_cmd

from app.services.summary_reference_config import SummaryReferenceConfig


@dataclass
class ClassifyResult:
    file: str
    classification: str
    confidence: str
    total_pages: int
    pages_analyzed: int
    avg_chars_per_page: float
    text_page_ratio: float
    has_embedded_fonts: bool
    image_dom_pages: int
    garbage_char_ratio: float
    signals: list = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class PageContent:
    page_number: int
    text: str
    tables: list
    method: str
    char_count: int


@dataclass
class ReadResult:
    file: str
    classification: str
    confidence: str
    total_pages: int
    pages_read: int
    method: str
    pages: list
    elapsed_seconds: float
    error: Optional[str] = None

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)


def _garbage_char_count(text: str) -> int:
    bad = {"Cc", "Cs", "Co", "Cn"}
    tofu = {"□", "☐", "￾", "￿", "�"}
    return sum(1 for char in text if unicodedata.category(char) in bad or char in tofu)


def _image_area_ratio(page: fitz.Page) -> float:
    page_area = page.rect.width * page.rect.height
    if page_area == 0:
        return 0.0
    image_area = sum(
        max(info["bbox"][2] - info["bbox"][0], 0) * max(info["bbox"][3] - info["bbox"][1], 0)
        for info in page.get_image_info(xrefs=True)
        if "bbox" in info
    )
    return min(image_area / page_area, 1.0)


def _fonts_ok(document: fitz.Document, pages_to_check: int) -> bool:
    bad_pages = 0
    checked = min(len(document), pages_to_check)
    for page_index in range(checked):
        for font in document.load_page(page_index).get_fonts(full=True):
            if font[1] == "" and font[2] not in ("Type3", ""):
                bad_pages += 1
                break
    return (bad_pages / checked) < 0.3 if checked else True


def _is_legacy_vietnamese_font(text: str) -> bool:
    if len(text) < 50:
        return False
    tcvn3_markers = set("µ¸¹²³¾»¼½¿ÖÊËÌÍÎÏÐÑÒÓÔÕÙÚÛÜÝàáâãäåæèéêëìíîïðñòóôõöùúûüý")
    latin_ext = sum(1 for char in text if " " <= char <= "ÿ")
    marker_hits = sum(1 for char in text if char in tcvn3_markers)
    ratio_latin = latin_ext / len(text)
    ratio_marker = marker_hits / len(text)
    return ratio_latin > 0.08 and ratio_marker > 0.03


def classify_pdf(pdf_path: str, cfg: SummaryReferenceConfig) -> ClassifyResult:
    if not os.path.exists(pdf_path):
        return ClassifyResult(
            file=pdf_path,
            classification="OCR required",
            confidence="low",
            total_pages=0,
            pages_analyzed=0,
            avg_chars_per_page=0,
            text_page_ratio=0,
            has_embedded_fonts=False,
            image_dom_pages=0,
            garbage_char_ratio=0,
            error=f"Không tìm thấy file: {pdf_path}",
        )

    try:
        document = fitz.open(pdf_path)
    except Exception as error:
        return ClassifyResult(
            file=pdf_path,
            classification="OCR required",
            confidence="low",
            total_pages=0,
            pages_analyzed=0,
            avg_chars_per_page=0,
            text_page_ratio=0,
            has_embedded_fonts=False,
            image_dom_pages=0,
            garbage_char_ratio=0,
            error=f"Không mở được file: {error}",
        )

    total_pages = len(document)
    if total_pages == 0:
        document.close()
        return ClassifyResult(
            file=pdf_path,
            classification="OCR required",
            confidence="low",
            total_pages=0,
            pages_analyzed=0,
            avg_chars_per_page=0,
            text_page_ratio=0,
            has_embedded_fonts=False,
            image_dom_pages=0,
            garbage_char_ratio=0,
            error="PDF không có trang nào.",
        )

    pages_to_analyze = min(total_pages, cfg.max_pages_to_analyze)
    total_chars = 0
    total_garbage = 0
    pages_with_text = 0
    image_dominant_pages = 0
    sample_text = ""

    for page_index in range(pages_to_analyze):
        page = document.load_page(page_index)
        text = page.get_text().strip()
        total_chars += len(text)
        total_garbage += _garbage_char_count(text)
        if len(text) >= cfg.min_avg_chars_per_page:
            pages_with_text += 1
        if _image_area_ratio(page) >= cfg.image_area_ratio_threshold:
            image_dominant_pages += 1
        if page_index < 3:
            sample_text += text

    avg_chars = total_chars / pages_to_analyze
    text_ratio = pages_with_text / pages_to_analyze
    garbage_ratio = total_garbage / max(total_chars, 1)
    fonts_ok = _fonts_ok(document, pages_to_analyze)
    legacy_font = _is_legacy_vietnamese_font(sample_text)
    document.close()

    bad_signals: list[str] = []
    good_signals: list[str] = []
    if avg_chars < cfg.min_avg_chars_per_page:
        bad_signals.append(f"Ký tự TB/trang thấp ({avg_chars:.0f} < {cfg.min_avg_chars_per_page}).")
    else:
        good_signals.append(f"Ký tự TB/trang đủ lớn ({avg_chars:.0f}).")

    if text_ratio < cfg.min_text_page_ratio:
        bad_signals.append(f"Chỉ {text_ratio * 100:.0f}% trang có văn bản (ngưỡng {cfg.min_text_page_ratio * 100:.0f}%).")
    else:
        good_signals.append(f"{text_ratio * 100:.0f}% trang có văn bản.")

    if image_dominant_pages / pages_to_analyze > 0.5:
        bad_signals.append(f"{image_dominant_pages}/{pages_to_analyze} trang bị ảnh phủ ≥ {cfg.image_area_ratio_threshold * 100:.0f}% diện tích.")
    elif image_dominant_pages > 0:
        good_signals.append(f"Có {image_dominant_pages} trang ảnh lớn nhưng không chiếm đa số.")

    if not fonts_ok:
        bad_signals.append("Nhiều font không nhúng → ký tự có thể bị lỗi.")
    else:
        good_signals.append("Font nhúng đầy đủ.")

    if garbage_ratio > cfg.max_garbage_char_ratio:
        bad_signals.append(f"Ký tự rác cao ({garbage_ratio * 100:.1f}%) → text bị mã hoá sai.")
    else:
        good_signals.append(f"Ký tự rác thấp ({garbage_ratio * 100:.1f}%).")

    if legacy_font:
        bad_signals.append("Phát hiện font encoding cũ (TCVN3/VNI/ABC) → text bị sai ký tự, cần OCR.")
    else:
        good_signals.append("Encoding Unicode chuẩn, text đọc được bình thường.")

    if legacy_font:
        classification, confidence = "OCR required", "high"
    elif len(bad_signals) >= 3:
        classification, confidence = "OCR required", "high"
    elif len(bad_signals) == 2:
        classification, confidence = "OCR required", "medium"
    elif len(bad_signals) == 1:
        classification, confidence = "OCR required", "low"
    else:
        classification, confidence = "No OCR needed", "high"

    signals = bad_signals + [f"[OK] {signal}" for signal in good_signals]
    if len(bad_signals) == 1 and not legacy_font:
        signals.insert(0, "⚠️ Chỉ 1 tín hiệu cần OCR — nên kiểm tra thủ công.")

    return ClassifyResult(
        file=pdf_path,
        classification=classification,
        confidence=confidence,
        total_pages=total_pages,
        pages_analyzed=pages_to_analyze,
        avg_chars_per_page=avg_chars,
        text_page_ratio=text_ratio,
        has_embedded_fonts=fonts_ok,
        image_dom_pages=image_dominant_pages,
        garbage_char_ratio=garbage_ratio,
        signals=signals,
    )


def _detect_two_columns(page, min_gap: int = 40) -> Optional[float]:
    words = page.extract_words()
    if len(words) < 20:
        return None
    page_width = page.width
    n_bins = 20
    bin_width = page_width / n_bins
    counts = [0] * n_bins
    for word in words:
        center_x = (word["x0"] + word["x1"]) / 2
        index = min(int(center_x / bin_width), n_bins - 1)
        counts[index] += 1
    lo = n_bins // 4
    hi = 3 * n_bins // 4
    max_count = max(counts) or 1
    threshold = max_count * 0.1
    best_start, best_len = -1, 0
    current_start, current_len = -1, 0
    for index in range(lo, hi):
        if counts[index] <= threshold:
            if current_len == 0:
                current_start = index
            current_len += 1
            if current_len > best_len:
                best_len = current_len
                best_start = current_start
        else:
            current_len = 0
    if best_len < 1:
        return None
    gap_center = (best_start + best_len / 2) * bin_width
    left_words = sum(1 for word in words if word["x1"] < gap_center)
    right_words = sum(1 for word in words if word["x0"] > gap_center)
    if left_words < 5 or right_words < 5:
        return None
    return gap_center


def _extract_two_column_text(page, split_x: float, cfg: SummaryReferenceConfig) -> tuple[str, list]:
    page_height = page.height
    page_width = page.width
    left_page = page.crop((0, 0, split_x, page_height))
    right_page = page.crop((split_x, 0, page_width, page_height))
    left_text = (left_page.extract_text(layout=cfg.preserve_layout) or "").strip()
    right_text = (right_page.extract_text(layout=cfg.preserve_layout) or "").strip()
    text = left_text
    if right_text:
        text = text + "\n\n" + right_text if text else right_text
    tables = []
    if cfg.extract_tables:
        for column_page in (left_page, right_page):
            for table in column_page.extract_tables() or []:
                if table:
                    tables.append(table)
    return text, tables


def _read_direct(pdf_path: str, cfg: SummaryReferenceConfig) -> list:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        limit = min(len(pdf.pages), cfg.max_pages) if cfg.max_pages else len(pdf.pages)
        for page_index in range(limit):
            page = pdf.pages[page_index]
            split_x = _detect_two_columns(page)
            is_two_column = split_x is not None
            if is_two_column:
                text, tables = _extract_two_column_text(page, split_x, cfg)
                method_label = "direct-2col"
            else:
                text = (page.extract_text(layout=cfg.preserve_layout) or "").strip()
                tables = [table for table in (page.extract_tables() or []) if table] if cfg.extract_tables else []
                method_label = "direct-1col"
            pages.append(PageContent(page_number=page_index + 1, text=text, tables=tables, method=method_label, char_count=len(text)))
    sample = " ".join(page.text for page in pages[:3])
    if _is_legacy_vietnamese_font(sample):
        raise ValueError("Text trích ra bị lỗi encoding (TCVN3/VNI/ABC). Chuyển sang OCR để đọc chính xác.")
    return pages


def _read_ocr(pdf_path: str, cfg: SummaryReferenceConfig) -> list:
    _ensure_tesseract_command()
    try:
        images = convert_from_path(pdf_path, dpi=cfg.ocr_dpi, last_page=cfg.max_pages)
    except Exception as error:
        message = str(error)
        if "poppler" in message.lower() or "PDFInfoNotInstalledError" in message:
            raise RuntimeError(
                "OCR cần Poppler (pdfinfo/pdftoppm) nhưng máy bạn chưa cài hoặc chưa có trong PATH. "
                "Hãy cài Poppler for Windows và thêm thư mục bin vào PATH, rồi restart terminal/server."
            ) from error
        raise

    pages = []
    for page_index, image in enumerate(images):
        try:
            text = pytesseract.image_to_string(image, lang=cfg.ocr_language, config="--oem 3 --psm 3").strip()
        except Exception as error:
            message = str(error)
            if "tesseract is not installed" in message.lower() or "tesseractnotfounderror" in message.lower():
                raise RuntimeError(
                    "OCR cần Tesseract nhưng máy bạn chưa cài hoặc chưa có trong PATH. "
                    "Hãy cài Tesseract-OCR và restart terminal/server."
                ) from error
            raise
        pages.append(PageContent(page_number=page_index + 1, text=text, tables=[], method="ocr", char_count=len(text)))
    return pages


def read_pdf(pdf_path: str, cfg: SummaryReferenceConfig, force: Optional[str] = None) -> ReadResult:
    started_at = time.time()
    classification = classify_pdf(pdf_path, cfg)
    if classification.error:
        return ReadResult(
            file=pdf_path,
            classification="unknown",
            confidence="low",
            total_pages=0,
            pages_read=0,
            method="none",
            pages=[],
            elapsed_seconds=time.time() - started_at,
            error=classification.error,
        )

    method = force if force else ("direct" if classification.classification == "No OCR needed" else "ocr")
    try:
        pages = _read_direct(pdf_path, cfg) if method == "direct" else _read_ocr(pdf_path, cfg)
    except Exception as error:
        if method == "direct":
            try:
                pages = _read_ocr(pdf_path, cfg)
                method = "ocr"
            except Exception as ocr_error:
                return ReadResult(
                    file=pdf_path,
                    classification=classification.classification,
                    confidence=classification.confidence,
                    total_pages=classification.total_pages,
                    pages_read=0,
                    method="ocr",
                    pages=[],
                    elapsed_seconds=time.time() - started_at,
                    error=str(ocr_error),
                )
        else:
            return ReadResult(
                file=pdf_path,
                classification=classification.classification,
                confidence=classification.confidence,
                total_pages=classification.total_pages,
                pages_read=0,
                method=method,
                pages=[],
                elapsed_seconds=time.time() - started_at,
                error=str(error),
            )

    return ReadResult(
        file=pdf_path,
        classification=classification.classification,
        confidence=classification.confidence,
        total_pages=classification.total_pages,
        pages_read=len(pages),
        method=method,
        pages=pages,
        elapsed_seconds=time.time() - started_at,
    )


def _words_to_lines(words: list, y_tol: float = 3.0) -> str:
    if not words:
        return ""
    words = sorted(words, key=lambda word: (word[1], word[0]))
    lines = []
    current_line = []
    current_y = None
    for word in words:
        _, y0, _, _, token = word[:5]
        if current_y is None or abs(y0 - current_y) <= y_tol:
            current_line.append(word)
            current_y = y0 if current_y is None else (current_y * 0.8 + y0 * 0.2)
        else:
            current_line = sorted(current_line, key=lambda item: item[0])
            lines.append(" ".join(str(item[4]) for item in current_line))
            current_line = [word]
            current_y = y0
    if current_line:
        current_line = sorted(current_line, key=lambda item: item[0])
        lines.append(" ".join(str(item[4]) for item in current_line))
    return "\n".join(lines)


def _detect_two_column_split(words: list, page_width: float) -> Optional[float]:
    if len(words) < 80:
        return None
    centers = [float((word[0] + word[2]) / 2) for word in words]
    n_bins = 32
    counts = [0] * n_bins
    for x in centers:
        index = min(n_bins - 1, max(0, int(x / page_width * n_bins)))
        counts[index] += 1
    lo = int(n_bins * 0.35)
    hi = int(n_bins * 0.65)
    max_count = max(counts) or 1
    threshold = max(2, max_count * 0.18)
    best_start, best_len = -1, 0
    current_start, current_len = -1, 0
    for index in range(lo, hi):
        if counts[index] <= threshold:
            if current_len == 0:
                current_start = index
            current_len += 1
            if current_len > best_len:
                best_start, best_len = current_start, current_len
        else:
            current_len = 0
    if best_len < 1:
        return None
    split_x = (best_start + best_len / 2) / n_bins * page_width
    left = sum(1 for x in centers if x < split_x)
    right = sum(1 for x in centers if x >= split_x)
    if left < 30 or right < 30:
        return None
    if min(left, right) / max(left, right) < 0.25:
        return None
    return split_x


def _page_text_by_columns(page) -> str:
    words = page.get_text("words")
    if not words:
        return page.get_text("text", sort=True) or ""
    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    words = [word for word in words if page_height * 0.035 <= float(word[1]) <= page_height * 0.965]
    split_x = _detect_two_column_split(words, page_width)
    if split_x is None:
        return _words_to_lines(words)
    left = [word for word in words if (float(word[0]) + float(word[2])) / 2 < split_x]
    right = [word for word in words if (float(word[0]) + float(word[2])) / 2 >= split_x]
    return _words_to_lines(left) + "\n\n" + _words_to_lines(right)


def read_pdf_text_pymupdf(pdf_path: str, max_pages: Optional[int] = None) -> str:
    pages = []
    with fitz.open(pdf_path) as document:
        limit = min(document.page_count, max_pages) if max_pages else document.page_count
        for page_index in range(limit):
            text = _page_text_by_columns(document.load_page(page_index))
            if text and text.strip():
                pages.append(text)
    return "\n\n".join(pages)


def get_pdf_text_smart(pdf_path: str, cfg: SummaryReferenceConfig) -> str:
    classification = classify_pdf(pdf_path, cfg)
    if classification.error:
        raise RuntimeError(f"Không đọc được PDF: {classification.error}")
    if classification.classification == "No OCR needed":
        return read_pdf_text_pymupdf(pdf_path, max_pages=cfg.max_pages)
    pages = _read_ocr(pdf_path, cfg)
    return "\n\n".join(page.text for page in pages if page.text)
