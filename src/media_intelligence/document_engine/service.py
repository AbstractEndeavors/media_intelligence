"""One extraction implementation shared by Media, tools and document consumers."""

from __future__ import annotations
import hashlib, os, time
from dataclasses import asdict
from pathlib import Path
from .model import Document, Page, Limits
from .store import ArtifactStore, identity
from . import native


def fingerprint(path: Path, limits: Limits):
    if not path.is_file():
        raise FileNotFoundError("Document source does not exist")
    if path.stat().st_size > limits.max_bytes:
        raise ValueError("Document exceeds its file-size limit")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            size += len(part)
            if size > limits.max_bytes:
                raise ValueError("Document exceeds its file-size limit")
            digest.update(part)
    return digest.hexdigest()


def extract_document(
    source,
    *,
    store_root=None,
    ocr="auto",
    backend=None,
    limits=None,
    refresh=False,
    progress=None,
    cancelled=None,
):
    if ocr not in ("auto", "off", "force"):
        raise ValueError("ocr must be auto, off or force")
    path = Path(source).expanduser().resolve()
    limits = limits or Limits()
    import math

    for name, value in asdict(limits).items():
        if (
            (name != "deadline_seconds" and not isinstance(value, int))
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            or (name != "max_ocr_pages" and value == 0)
        ):
            raise ValueError(
                "Document limits must be positive and finite (max_ocr_pages may be zero)"
            )
    if backend is None and ocr != "off":
        from .ocr import HugpyOCR

        backend = HugpyOCR()
    digest = fingerprint(path, limits)
    options = {
        "ocr": ocr,
        "backend": backend.identity if backend else None,
        "limits": asdict(limits),
    }
    key = identity(path, digest, options)
    store = ArtifactStore(
        store_root
        or os.environ.get("HUGPY_DOCUMENTS_HOME")
        or path.parent / ".documents"
    )
    ext = path.suffix.lower()
    kind = ext.lstrip(".") or "text"
    with store.lock(key):
        cached = store.load(key) if not refresh else None
        if cached and cached.status == "complete":
            cached.cache_hit = True
            return cached.payload()
        doc = Document(
            key,
            digest,
            path.name,
            kind,
            meta={
                "source_key": hashlib.sha256(str(path).encode()).hexdigest(),
                "options": options,
            },
        )
        deadline = time.monotonic() + limits.deadline_seconds
        previous = {p.index: p for p in cached.pages} if cached else {}
        meta = {}
        try:
            if ext == ".pdf":
                from .pdf import pdf_pages

                pages = pdf_pages(path, limits, backend, ocr, deadline, meta, previous)
            elif ext == ".docx":
                pages, meta = native.docx_pages(path, limits)
            elif ext in (".xlsx", ".xlsm"):
                pages, meta = native.xlsx_pages(path, limits)
            elif ext == ".pptx":
                pages, meta = native.pptx_pages(path, limits)
            elif ext in (".doc", ".xls", ".ppt"):
                raise ValueError(
                    f"Legacy binary {ext} is unsupported; save as "
                    + {".doc": ".docx", ".xls": ".xlsx", ".ppt": ".pptx"}[ext]
                )
            elif ext in native.TEXT_EXT:
                pages = [native.text_page(path, limits)]
            else:
                raise ValueError(
                    "Unsupported document format: " + (ext or "(no extension)")
                )
            chars = 0
            for page in pages:
                if cancelled and cancelled():
                    doc.status = "cancelled"
                    doc.warnings.append("Extraction cancelled")
                    break
                if time.monotonic() > deadline:
                    doc.status = "cancelled"
                    doc.warnings.append("Document processing deadline reached")
                    break
                if len(doc.pages) >= limits.max_pages:
                    doc.truncated = True
                    doc.warnings.append("Document reached its page limit")
                    break
                left = limits.max_chars - chars
                if len(page.text) > left:
                    page.text = page.text[: max(0, left)]
                    page.status = "partial"
                    page.warnings.append("Document reached its character limit")
                    # Do not leave oversized text hidden in structured blocks.
                    page.blocks = []
                    doc.truncated = True
                chars += len(page.text)
                doc.pages.append(page)
                doc.meta.update(meta)
                doc.pages_total = int(meta.get("page_count", len(doc.pages)))
                doc.status = "partial"  # A checkpoint is never a completed artifact.
                store.save(doc)
                if progress:
                    progress(
                        {
                            "artifact_id": key,
                            "page": page.index + 1,
                            "status": page.status,
                        }
                    )
                if page.status == "cancelled":
                    doc.status = "cancelled"
                    break
                if doc.truncated:
                    break
            doc.meta.update(meta)
            doc.pages_total = int(meta.get("page_count", len(doc.pages)))
            if doc.status != "cancelled":
                complete = (
                    not doc.truncated
                    and len(doc.pages) == doc.pages_total
                    and all(p.status == "complete" for p in doc.pages)
                )
                doc.status = "complete" if complete else "partial"
                if len(doc.pages) < doc.pages_total:
                    doc.warnings.append(
                        f"Processed {len(doc.pages)}/{doc.pages_total} source pages"
                    )
                if not any(p.text for p in doc.pages) and any(
                    p.status in ("failed", "needs_ocr") for p in doc.pages
                ):
                    doc.status = "failed"
            if not any(p.text.strip() for p in doc.pages):
                doc.error = "No readable document text was extracted"
        except Exception as exc:
            doc.status = "partial" if any(p.text for p in doc.pages) else "failed"
            doc.error = " ".join(str(exc).split())[:400]
            doc.warnings.append(doc.error)
        # The source may have changed while being processed. Never cache it as
        # the artifact of its previous contents.
        try:
            unchanged = fingerprint(path, limits) == digest
        except (OSError, ValueError):
            unchanged = False
        if not unchanged:
            doc.status = "failed"
            doc.error = "Source changed during extraction; retry the document"
            doc.warnings.append(doc.error)
        store.save(doc)
        return doc.payload()


def load_document(source, artifact_id, *, store_root=None):
    path = Path(source).expanduser().resolve()
    store = ArtifactStore(
        store_root
        or os.environ.get("HUGPY_DOCUMENTS_HOME")
        or path.parent / ".documents"
    )
    doc = store.load(artifact_id)
    if doc is None:
        raise FileNotFoundError("Document artifact was not found")
    if (
        doc.meta.get("source_key") != hashlib.sha256(str(path).encode()).hexdigest()
        or fingerprint(path, Limits()) != doc.source_sha256
    ):
        raise PermissionError("Document artifact does not match this source")
    return doc.payload()


def read_page(source, artifact_id, page, *, store_root=None):
    doc = load_document(source, artifact_id, store_root=store_root)
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("page must be a positive, one-based integer")
    found = next((p for p in doc["pages"] if p["index"] == page - 1), None)
    if found is None:
        raise ValueError("This page is not available in the artifact")
    return {"artifact_id": artifact_id, "page": found, "document_status": doc["status"]}


def search_document(source, artifact_id, query, *, limit=20, store_root=None):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("A search query is required")
    doc = load_document(source, artifact_id, store_root=store_root)
    hits = []
    needle = query.casefold()
    for page in doc["pages"]:
        for bi, block in enumerate(page.get("blocks") or [{"text": page["text"]}]):
            text = block.get("text") or ""
            if needle in text.casefold():
                offset = text.casefold().find(needle)
                hits.append(
                    {
                        "page": page["index"] + 1,
                        "block": bi,
                        "text": text[max(0, offset - 160) : offset + len(query) + 320],
                        "bbox": block.get("bbox"),
                        "source": block.get("source"),
                        "method": page["method"],
                    }
                )
                if len(hits) >= max(1, min(int(limit), 100)):
                    return {"artifact_id": artifact_id, "hits": hits}
    return {"artifact_id": artifact_id, "hits": hits}
