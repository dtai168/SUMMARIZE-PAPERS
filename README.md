# Summarize Project 

Dự án nghiên cứu (research-first) về **tóm tắt tài liệu PDF (ưu tiên tiếng Việt)** và **chat/Q&A theo hướng RAG**.

Repo hiện tại chủ yếu gồm các notebook để thử nghiệm pipeline và chưa phải một web app hoàn chỉnh (chưa có scaffold, test suite, hay build config chuẩn).

## Nội dung chính

- **PDF ingestion & summarization pipeline**: phân loại PDF → trích xuất (direct/OCR) → làm sạch → chọn đoạn quan trọng (extractive) → (tuỳ chọn) đánh bóng (abstractive)
- **RAG prototype**: nhúng (embeddings) → lưu vector (Chroma) → truy hồi (retrieval) → sinh câu trả lời (LLM)

## Cấu trúc thư mục

- `backend/dataops-aisumary-9.ipynb`: notebook chính cho pipeline ingest + tóm tắt PDF
- `backend/RAG.ipynb`: notebook cho prototype RAG (chat với nội dung bài/tài liệu)
- `frontend/resend.com_.png`: hình tham khảo style UI (hướng SaaS tối giản)

## Cách chạy

### 1) Mở và chạy notebook
Chạy tương tác trong Jupyter / VS Code Notebook / Colab / Kaggle:
- `backend/dataops-aisumary-9.ipynb`
- `backend/RAG.ipynb`

### 2) Cài dependencies (tham khảo theo notebook)
> Lưu ý: các notebook có thể chứa lệnh cài đặt khác nhau tuỳ môi trường (Colab/Kaggle vs local). Đây là phần tóm tắt các dependency được sử dụng trong notebook.

#### PDF extraction / OCR (`backend/dataops-aisumary-9.ipynb`)
Python packages:
- `PyMuPDF` (fitz)
- `pdfplumber`
- `pdf2image`
- `pytesseract`

System packages (Linux/Colab):
- `tesseract-ocr`, `tesseract-ocr-vie`, `poppler-utils`

LLM / finetune stack (tuỳ chọn theo notebook):
- `unsloth`
- `xformers`, `trl<0.9.0`, `peft`, `accelerate`, `bitsandbytes`

#### RAG (`backend/RAG.ipynb`)
- `langchain`, `langchain-community`, `langchain-huggingface`
- `sentence-transformers`
- `chromadb`

## Ghi chú quan trọng

- Pipeline hiện tại có nhiều xử lý đặc thù cho PDF tiếng Việt (OCR `vie+eng`, làm sạch text, hỗ trợ PDF hai cột, v.v.).
- Notebook `backend/RAG.ipynb` có thể gặp cảnh báo deprecation về import Chroma; nếu productionize, nên cập nhật theo khuyến nghị trong cảnh báo.

## Git / GitHub

Khuyến nghị **không commit** các file/ thư mục sau:
- `.env`, credential, API keys
- `.venv/`, `venv/`, `__pycache__/`
- `.ipynb_checkpoints/`
- `node_modules/`, `dist/`, `build/`

---

