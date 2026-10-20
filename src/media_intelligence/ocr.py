"""Small OCR boundary. Model execution is owned by Hugpy workers."""

from __future__ import annotations
import mimetypes
from pathlib import Path
from .document_engine.ocr import HugpyOCR
from .document_engine.model import OCRBackend, OCRResult

__all__ = [
    "image_to_text",
    "recognize_image",
    "image_to_text_layout",
    "HugpyOCR",
    "OCRBackend",
    "OCRResult",
]


def recognize_image(image_path, *, backend=None) -> OCRResult:
    p = Path(image_path)
    if p.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("OCR image exceeds 20 MB")
    mime = mimetypes.guess_type(p.name)[0]
    if mime not in ("image/png", "image/jpeg", "image/webp", "image/gif", "image/bmp"):
        raise ValueError("Unsupported OCR image type")
    return (backend or HugpyOCR()).recognize(p.read_bytes(), mime, timeout=180)


def image_to_text(image_path, preprocess=True, *, backend=None):
    """Compatibility text-only helper; use recognize_image for coverage metadata."""
    return recognize_image(image_path, backend=backend).text


def image_to_text_layout(image_path, config=None, chain=None, *, backend=None):
    # A full-page vision transcription cannot claim word-level geometry.
    result = recognize_image(image_path, backend=backend)
    text = result.text
    return {
        "text": text,
        "needs_review": True,
        "complete": bool(text.strip()) and not result.truncated and not result.warnings,
        "status": "failed"
        if not text.strip()
        else "partial"
        if result.truncated or result.warnings
        else "complete",
        "warnings": result.warnings,
        "method": result.method,
        "blocks": [
            {"type": "ocr_markdown", "text": text, "bbox": None, "inferred": True}
        ],
    }
