"""Shared document capability: artifacts, native readers and managed OCR.

The old abstract_pdfs/abstract_ocr pipelines are deliberately not imported.
Callers own source authorization; hosted Media applies its upload jail before
calling this library. Page references are one-based at read/search boundaries.
"""

from __future__ import annotations
from .document_engine import (
    extract_document,
    load_document,
    read_page,
    search_document,
    Limits,
    OCRBackend,
    OCRResult,
)
from .document_engine.job import run_job

__all__ = [
    "extract_document",
    "load_document",
    "read_page",
    "search_document",
    "inspect_document",
    "process_pdf",
    "process_pdfs",
    "process_all_pdfs",
    "pdf_pages",
    "Limits",
    "OCRBackend",
    "OCRResult",
    "run_job",
]


def inspect_document(source):
    from pathlib import Path
    from .document_engine.service import fingerprint

    p = Path(source).resolve()
    digest = fingerprint(p, Limits())
    return {
        "name": p.name,
        "bytes": p.stat().st_size,
        "source_sha256": digest,
        "kind": p.suffix.lower().lstrip("."),
        "supported": p.suffix.lower()
        in {
            ".pdf",
            ".docx",
            ".xlsx",
            ".xlsm",
            ".pptx",
            ".txt",
            ".md",
            ".csv",
            ".tsv",
            ".json",
            ".xml",
            ".log",
            ".text",
            ".rst",
            ".markdown",
            ".yaml",
            ".yml",
        },
    }


def process_pdf(pdf_path, **kwargs):
    return extract_document(pdf_path, **kwargs)


def process_pdfs(pdf_paths, **kwargs):
    return [process_pdf(path, **kwargs) for path in pdf_paths]


def process_all_pdfs(directory, **kwargs):
    from pathlib import Path

    return process_pdfs(sorted(Path(directory).rglob("*.pdf")), **kwargs)


def pdf_pages(pdf_path, *, artifact_id=None, **kwargs):
    result = (
        load_document(pdf_path, artifact_id, **kwargs)
        if artifact_id
        else extract_document(pdf_path, **kwargs)
    )
    return result["pages"], result["text"] or None
