from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz
import pytesseract
from pdf2image import convert_from_path

from app.core.config import get_settings


@dataclass
class Config:
    ocr_language: str = "vie+eng"
    ocr_dpi: int = 300
    preserve_layout: bool = True
    max_pages: Optional[int] = None
    min_avg_chars_per_page: int = 100
    min_text_page_ratio: float = 0.5
    image_area_ratio_threshold: float = 0.8
    max_garbage_char_ratio: float = 0.1
    max_pages_to_analyze: int = 20


@dataclass
class ReadResult:
    file: str
    total_pages: int
    pages_read: int
    method: str
    full_text: str


@dataclass
class ClassifyResult:
    classification: str
    confidence: str
    total_pages: int
    pages_analyzed: int
    avg_chars_per_page: float
    text_page_ratio: float
    has_embedded_fonts: bool
    image_dom_pages: int
    garbage_char_ratio: float
    legacy_vietnamese_font: bool


def build_pdf_config() -> Config:
    settings = get_settings()
    return Config(
        ocr_language=settings.pdf_ocr_language,
        ocr_dpi=settings.pdf_ocr_dpi,
        preserve_layout=settings.pdf_preserve_layout,
        max_pages=settings.pdf_max_pages,
        min_avg_chars_per_page=settings.pdf_min_avg_chars_per_page,
        min_text_page_ratio=settings.pdf_min_text_page_ratio,
        image_area_ratio_threshold=settings.pdf_image_area_ratio_threshold,
        max_garbage_char_ratio=settings.pdf_max_garbage_char_ratio,
        max_pages_to_analyze=settings.pdf_max_pages_to_analyze,
    )


def _words_to_lines(words: list, y_tol: float = 3.0) -> str:
    if not words:
        return ""
    words = sorted(words, key=lambda item: (item[1], item[0]))
    lines: list[str] = []
    current_line = []
    current_y = None

    for word in words:
        _, y0, _, _, _ = word[:5]
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
    for i in range(lo, hi):
        if counts[i] <= threshold:
            if current_len == 0:
                current_start = i
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


def _page_text_by_columns(page: fitz.Page) -> str:
    words = page.get_text("words")
    if not words:
        return page.get_text("text", sort=True) or ""

    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    filtered_words = [
        word for word in words if page_height * 0.035 <= float(word[1]) <= page_height * 0.965
    ]
    split_x = _detect_two_column_split(filtered_words, page_width)
    if split_x is None:
        return _words_to_lines(filtered_words)

    left_words = [word for word in filtered_words if (float(word[0]) + float(word[2])) / 2 < split_x]
    right_words = [word for word in filtered_words if (float(word[0]) + float(word[2])) / 2 >= split_x]
    return _words_to_lines(left_words) + "\n\n" + _words_to_lines(right_words)


def _garbage_char_count(text: str) -> int:
    bad_categories = {"Cc", "Cs", "Co", "Cn"}
    tofu_chars = {"□", "☐", "￾", "￿", "�"}
    return sum(1 for char in text if unicodedata.category(char) in bad_categories or char in tofu_chars)


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


def classify_pdf(pdf_path: str, cfg: Config) -> ClassifyResult:
    with fitz.open(pdf_path) as document:
        total_pages = len(document)
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

        avg_chars = total_chars / pages_to_analyze if pages_to_analyze else 0.0
        text_ratio = pages_with_text / pages_to_analyze if pages_to_analyze else 0.0
        garbage_ratio = total_garbage / max(total_chars, 1)
        fonts_ok = _fonts_ok(document, pages_to_analyze)
        legacy_font = _is_legacy_vietnamese_font(sample_text)

        bad_signals = 0
        if avg_chars < cfg.min_avg_chars_per_page:
            bad_signals += 1
        if text_ratio < cfg.min_text_page_ratio:
            bad_signals += 1
        if image_dominant_pages / max(pages_to_analyze, 1) > 0.5:
            bad_signals += 1
        if not fonts_ok:
            bad_signals += 1
        if garbage_ratio > cfg.max_garbage_char_ratio:
            bad_signals += 1

        if legacy_font:
            classification, confidence = "ocr", "high"
        elif bad_signals >= 3:
            classification, confidence = "ocr", "high"
        elif bad_signals == 2:
            classification, confidence = "ocr", "medium"
        elif bad_signals == 1:
            classification, confidence = "ocr", "low"
        else:
            classification, confidence = "direct", "high"

        return ClassifyResult(
            classification=classification,
            confidence=confidence,
            total_pages=total_pages,
            pages_analyzed=pages_to_analyze,
            avg_chars_per_page=avg_chars,
            text_page_ratio=text_ratio,
            has_embedded_fonts=fonts_ok,
            image_dom_pages=image_dominant_pages,
            garbage_char_ratio=garbage_ratio,
            legacy_vietnamese_font=legacy_font,
        )


def _read_direct(pdf_path: str, cfg: Config) -> ReadResult:
    normalized_path = str(Path(pdf_path))
    pages: list[str] = []

    with fitz.open(normalized_path) as document:
        limit = min(document.page_count, cfg.max_pages) if cfg.max_pages else document.page_count
        for page_index in range(limit):
            page = document.load_page(page_index)
            page_text = _page_text_by_columns(page).strip()
            if page_text:
                pages.append(page_text)

        full_text = "\n\n".join(pages).strip()
        if _is_legacy_vietnamese_font(" ".join(pages[:3])):
            raise ValueError("Detected legacy Vietnamese font encoding in direct extraction")
        return ReadResult(
            file=normalized_path,
            total_pages=document.page_count,
            pages_read=limit,
            method="direct-pymupdf-smart",
            full_text=full_text,
        )


def _read_ocr(pdf_path: str, cfg: Config, total_pages: int | None = None) -> ReadResult:
    normalized_path = str(Path(pdf_path))
    images = convert_from_path(normalized_path, dpi=cfg.ocr_dpi, last_page=cfg.max_pages)
    pages: list[str] = []
    for image in images:
        text = pytesseract.image_to_string(image, lang=cfg.ocr_language, config="--oem 3 --psm 3").strip()
        if text:
            pages.append(text)
    page_count = total_pages if total_pages is not None else len(images)
    return ReadResult(
        file=normalized_path,
        total_pages=page_count,
        pages_read=len(images),
        method="ocr-pytesseract",
        full_text="\n\n".join(pages).strip(),
    )


def get_pdf_text_smart(pdf_path: str, cfg: Config | None = None) -> ReadResult:
    settings = cfg or build_pdf_config()
    classification = classify_pdf(pdf_path, settings)

    if classification.classification == "direct":
        try:
            result = _read_direct(pdf_path, settings)
            if not result.full_text.strip():
                raise ValueError("Direct extraction produced empty text")
            return result
        except Exception:
            return _read_ocr(pdf_path, settings, total_pages=classification.total_pages)

    return _read_ocr(pdf_path, settings, total_pages=classification.total_pages)
