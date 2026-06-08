from dataclasses import dataclass
from typing import Optional


@dataclass
class SummaryReferenceConfig:
    min_avg_chars_per_page: int = 100
    min_text_page_ratio: float = 0.5
    image_area_ratio_threshold: float = 0.8
    max_garbage_char_ratio: float = 0.1
    max_pages_to_analyze: int = 20

    ocr_language: str = "vie+eng"
    ocr_dpi: int = 300
    extract_tables: bool = True
    preserve_layout: bool = True
    max_pages: Optional[int] = None


cfg = SummaryReferenceConfig(
    ocr_language="vie+eng",
    ocr_dpi=300,
    extract_tables=True,
    preserve_layout=True,
    max_pages=None,
)
