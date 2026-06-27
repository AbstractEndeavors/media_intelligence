"""Extraction + structuring layer (documents) — PDFs.

Canonical owner: ``abstract_pdfs``. Page-level decomposition (text + images),
manifest generation, OCR (delegating to ``abstract_ocr``), enrichment, and
static HTML (viewer + gallery).
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from ._lazy import require, soft_import

_PKG = "abstract_pdfs"
_LAYER = "documents"

__all__ = [
    "process_pdf",
    "process_pdfs",
    "process_all_pdfs",
    "generate_pdf",
    "pdf_pages",
    "DocumentPipeline",
    "SliceManager",
]


def process_pdf(pdf_path: str, **kwargs: Any) -> dict:
    """Process every page of one PDF (image→text→info→metadata→html + gallery)."""
    fn = require(_PKG, "process_pdf", layer=_LAYER)
    return fn(pdf_path, **kwargs)


def process_pdfs(pdf_paths: list[str], **kwargs: Any) -> list:
    """Batch process many PDFs with two-level parallelism (PDFs × pages)."""
    fn = require(_PKG, "process_pdfs", layer=_LAYER)
    return fn(pdf_paths, **kwargs)


def process_all_pdfs(directory: str, **kwargs: Any):
    """Discover and process every ``.pdf`` under ``directory``."""
    fn = require(_PKG, "process_all_pdfs", layer=_LAYER)
    return fn(directory, **kwargs)


def generate_pdf(pdf_path: str, **kwargs: Any) -> dict:
    """One-call end-to-end: slice + OCR + enriched manifests + viewer HTML."""
    mod = soft_import(_PKG + ".pipeline", layer=_LAYER)
    fn = getattr(mod, "generate_pdf", None) or require(_PKG, "generate_pdf", layer=_LAYER)
    return fn(pdf_path, **kwargs)


def _resolve_pdf_dir(pdf_path: str) -> Optional[str]:
    """Find the directory holding ``pages/`` for a processed PDF.

    ``process_pdf`` relocates ``<dir>/foo.pdf`` into ``<dir>/foo/foo.pdf`` and
    writes pages under ``<dir>/foo/pages/``. We check the relocated dir first,
    then the original dir, so this works whether or not relocation happened.
    """
    p = os.path.abspath(pdf_path)
    parent = os.path.dirname(p)
    stem = os.path.splitext(os.path.basename(p))[0]
    for candidate in (os.path.join(parent, stem), parent):
        if os.path.isdir(os.path.join(candidate, "pages")):
            return candidate
    return None


def pdf_pages(pdf_path: str) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Read back the per-page OCR'd text/info that ``process_pdf`` wrote to disk.

    Returns ``(pages, full_text)`` where ``pages`` is a list of
    ``{"index", "page", "text", "info"}`` dicts in page order, and ``full_text``
    is the pages joined. Reads the cached ``pages/NNNN/text.txt`` + ``info.json``
    layout directly — no re-OCR, no fragile deep imports. ``([], None)`` if the
    PDF hasn't been processed yet.
    """
    base = _resolve_pdf_dir(pdf_path)
    if base is None:
        return [], None
    pages_dir = os.path.join(base, "pages")
    # zero-padded names (0001, 0002, ...) so lexical sort == page order
    names = sorted(
        d for d in os.listdir(pages_dir) if os.path.isdir(os.path.join(pages_dir, d))
    )
    pages: list[dict[str, Any]] = []
    for i, name in enumerate(names):
        pdir = os.path.join(pages_dir, name)
        text_path = os.path.join(pdir, "text.txt")
        info_path = os.path.join(pdir, "info.json")
        text = ""
        if os.path.isfile(text_path):
            with open(text_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read().strip()
        info: dict[str, Any] = {}
        if os.path.isfile(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as fh:
                    info = json.load(fh)
            except Exception:
                info = {}
        pages.append(
            {"index": int(name) if name.isdigit() else i, "page": name, "text": text, "info": info}
        )
    full_text = "\n\n".join(p["text"] for p in pages if p["text"]).strip() or None
    return pages, full_text


def DocumentPipeline(*args: Any, **kwargs: Any):
    """Construct the per-PDF ``DocumentPipeline`` orchestrator."""
    cls = require(_PKG, "DocumentPipeline", layer=_LAYER)
    return cls(*args, **kwargs)


def SliceManager(*args: Any, **kwargs: Any):
    """Construct the slice-aware multi-engine column OCR ``SliceManager``."""
    cls = require(_PKG, "SliceManager", layer=_LAYER)
    return cls(*args, **kwargs)
