"""Извлечение текста из PDF-резюме."""
from __future__ import annotations

import io


def extract_text_from_pdf_bytes(data: bytes) -> str:
    """Извлекает текст из PDF (цифровой PDF; сканы без OCR не поддерживаются)."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text()
        except Exception:
            t = ""
        if t:
            parts.append(t)
    return "\n".join(parts).strip()
