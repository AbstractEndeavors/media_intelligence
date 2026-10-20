"""Structured documents with optional Hugpy-managed OCR; no abstract_ocr dependency."""

from .model import Document, Page, Limits, OCRResult, OCRBackend
from .service import extract_document, load_document, read_page, search_document

__all__ = [
    "Document",
    "Page",
    "Limits",
    "OCRResult",
    "OCRBackend",
    "extract_document",
    "load_document",
    "read_page",
    "search_document",
]
