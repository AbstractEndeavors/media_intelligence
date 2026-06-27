"""Structuring layer — normalize raw extraction output into the typed model.

This is the "structured over raw" hinge of the platform. It does not own a heavy
engine; it decomposes whatever the extract layer produced (PDF page dicts, a
whisper transcript, a list of frames) into the canonical :class:`MediaItem`
fields and builds a typed manifest dict ready for persistence.
"""
from __future__ import annotations

from typing import Any, Optional

from .schemas import MediaItem, MediaKind

__all__ = [
    "structure_item",
    "build_manifest",
    "build_document",
    "segments_from_transcript",
]


def segments_from_transcript(transcript: Any) -> list[dict[str, Any]]:
    """Flatten a whisper-style transcript into uniform text segments."""
    if not transcript:
        return []
    data = transcript
    if isinstance(transcript, dict):
        data = transcript.get("segments") or transcript.get("result") or []
    segments: list[dict[str, Any]] = []
    for i, seg in enumerate(data or []):
        if isinstance(seg, dict):
            segments.append(
                {
                    "index": i,
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": (seg.get("text") or "").strip(),
                }
            )
        else:
            segments.append({"index": i, "text": str(seg).strip()})
    return segments


def structure_item(item: MediaItem) -> MediaItem:
    """Decompose extraction outputs into the typed page/segment model in-place.

    - Video/audio: derive ``pages`` (segments) and ``text`` from the transcript.
    - PDF/image: ``pages``/``text`` are expected to already be populated by the
      document/OCR extractor; we only backfill ``text`` from pages if missing.
    Idempotent: safe to call repeatedly.
    """
    if item.kind in (MediaKind.VIDEO, MediaKind.AUDIO) and item.transcript and not item.pages:
        item.pages = segments_from_transcript(item.transcript)

    if not item.text and item.pages:
        item.text = "\n\n".join(
            (p.get("text") or "") for p in item.pages if isinstance(p, dict)
        ).strip() or None
    return item


def _text_chars(item: MediaItem) -> int:
    return len(item.text) if item.text else 0


def build_manifest(item: MediaItem, *, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Build the lean, JSONB-ready *index* record for a structured item.

    Deliberately excludes the full body text/pages/transcript — those live in the
    companion document record (:func:`build_document`) so "list / query metadata"
    operations stay cheap. ``text_chars`` and ``page_count`` are kept so the index
    is still useful for filtering/sorting without loading the document.
    """
    manifest: dict[str, Any] = {
        "media_id": item.media_id,
        "source": item.source,
        "kind": item.kind.value if isinstance(item.kind, MediaKind) else item.kind,
        "local_path": item.local_path,
        "title": item.title,
        "summary": item.summary,
        "keywords": item.keywords,
        "seo": item.seo,
        "page_count": len(item.pages),
        "text_chars": _text_chars(item),
        "has_transcript": item.transcript is not None,
        "assets": item.assets,
        "metadata": item.metadata,
    }
    if extra:
        manifest.update(extra)
    return manifest


def build_document(item: MediaItem, *, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Build the *full* canonical content record — the source of truth.

    Superset of the manifest plus the parsed body: ``text``, ``pages``/segments,
    and the raw ``transcript``. This is what aggregation, full-text search, and
    LLM-dataset builders read — one record per item, no re-stitching of per-owner
    on-disk files and no re-OCR/re-transcribe.
    """
    document = build_manifest(item)
    document.update(
        {
            "text": item.text,
            "pages": item.pages,
            "transcript": item.transcript,
            "frames": item.frames,
        }
    )
    if extra:
        document.update(extra)
    return document
