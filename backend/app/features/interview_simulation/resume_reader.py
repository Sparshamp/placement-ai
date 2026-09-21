# app/features/interview_simulation/resume_reader.py
import io

def extract_resume_text(raw_bytes: bytes, filename: str) -> str:
    name = filename.lower()

    if name.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages).strip()

    elif name.endswith(".docx"):
        from docx import Document
        doc = Document(io.BytesIO(raw_bytes))
        return "\n".join(p.text for p in doc.paragraphs).strip()

    elif name.endswith(".txt"):
        return raw_bytes.decode("utf-8", errors="ignore").strip()

    raise ValueError("Unsupported file format. Use .pdf, .docx, or .txt")