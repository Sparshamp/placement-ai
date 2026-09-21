"""Extract raw text from a resume file. Supports .docx, .pdf, .txt.

Uses pdfplumber (already in this project's interview feature) instead of
pdfminer so we do not add a duplicate PDF library.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

from docx import Document

SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".txt"}


def parse_docx_bytes(raw: bytes) -> str:
    doc = Document(io.BytesIO(raw))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def parse_pdf_bytes(raw: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    lines = [line.strip() for page in pages for line in page.splitlines() if line.strip()]
    return "\n".join(lines)


def parse_txt_bytes(raw: bytes) -> str:
    return raw.decode("utf-8", errors="ignore").strip()


def parse_resume_bytes(raw: bytes, filename: str) -> dict:
    """Parse uploaded resume bytes into the dict expected by process_one()."""
    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported file format. Use .pdf, .docx, or .txt")

    if ext == ".docx":
        text = parse_docx_bytes(raw)
    elif ext == ".pdf":
        text = parse_pdf_bytes(raw)
    else:
        text = parse_txt_bytes(raw)

    if not (text or "").strip():
        raise ValueError("Could not read any text from this resume. The file may be empty or image-only.")

    return {
        "filename": os.path.basename(filename) or "resume",
        "raw_text": text.strip(),
        "file_type": ext.lstrip("."),
    }
