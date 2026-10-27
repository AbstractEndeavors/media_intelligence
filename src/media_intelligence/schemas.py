"""Typed data model shared across the platform.

Principle #2 of the vision: *structured over raw*. Every stage reads and writes
these typed records instead of passing loose blobs around. Pure stdlib
dataclasses so importing the facade never costs more than the standard library.
"""

from __future__ import annotations

from .imports.constants import _IMAGE_EXTS, _VIDEO_EXTS, _AUDIO_EXTS, _DOC_EXTS

import enum
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

__all__ = [
    "MediaKind",
    "Stage",
    "MediaItem",
    "StageResult",
    "PipelineReport",
    "detect_media_kind",
]

# Extension → media kind. Kept deliberately small and explicit.


class MediaKind(str, enum.Enum):
    """The media types the platform converges on (vision: multimodal)."""

    PDF = "pdf"
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    URL = "url"
    UNKNOWN = "unknown"


class Stage(str, enum.Enum):
    """The six layers of the end-to-end pipeline, in order."""

    INGEST = "ingest"
    EXTRACT = "extract"
    STRUCTURE = "structure"
    ENRICH = "enrich"
    PERSIST = "persist"
    PUBLISH = "publish"


def detect_media_kind(source: str) -> MediaKind:
    """Best-effort classification of a source path or URL into a MediaKind."""
    if source is None:
        return MediaKind.UNKNOWN
    s = str(source).strip()
    lowered = s.lower()
    looks_like_url = lowered.startswith(("http://", "https://", "ftp://"))
    # Strip query/fragment before looking at the extension.
    path_part = lowered.split("?", 1)[0].split("#", 1)[0]
    _, ext = os.path.splitext(path_part)
    if ext in _DOC_EXTS:
        return MediaKind.PDF
    if ext in {
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
        ".rst",
    }:
        return MediaKind.DOCUMENT
    if ext in _IMAGE_EXTS:
        return MediaKind.IMAGE
    if ext in _VIDEO_EXTS:
        return MediaKind.VIDEO
    if ext in _AUDIO_EXTS:
        return MediaKind.AUDIO
    if looks_like_url:
        # A URL with no obvious media extension is treated as a fetchable source
        # (typically a video page handed to yt-dlp, or a web page to scrape).
        return MediaKind.URL
    return MediaKind.UNKNOWN


@dataclass
class MediaItem:
    """The unit of work that flows through the pipeline.

    ``source`` is the original input (path or URL). Subsequent stages populate
    the artifact fields; everything is optional so the same record serves PDFs,
    images, audio and video.
    """

    source: str
    kind: MediaKind = MediaKind.UNKNOWN
    # Local filesystem location once ingested/downloaded.
    local_path: Optional[str] = None
    # Stable id used to name the on-disk asset collection.
    media_id: Optional[str] = None

    # --- extraction outputs ---
    text: Optional[str] = None  # full extracted/transcribed text
    pages: list[dict[str, Any]] = field(default_factory=list)  # per-page/segment
    transcript: Optional[dict[str, Any]] = None  # whisper-style result
    frames: list[str] = field(default_factory=list)  # frame image paths

    # --- enrichment outputs ---
    summary: Optional[str] = None
    keywords: list[Any] = field(default_factory=list)
    title: Optional[str] = None
    seo: dict[str, Any] = field(default_factory=dict)

    # --- structure / persistence ---
    metadata: dict[str, Any] = field(default_factory=dict)
    assets: dict[str, str] = field(default_factory=dict)  # role -> path
    manifest_path: Optional[str] = None
    published: dict[str, str] = field(default_factory=dict)  # html/url outputs

    def __post_init__(self) -> None:
        if self.kind in (MediaKind.UNKNOWN, None):
            self.kind = detect_media_kind(self.source)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value if isinstance(self.kind, MediaKind) else self.kind
        return d


@dataclass
class StageResult:
    """Outcome of a single pipeline stage — drives idempotency/resume."""

    stage: Stage
    status: str = "pending"  # pending | ok | skipped | error
    detail: str = ""
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status in ("ok", "skipped")


@dataclass
class PipelineReport:
    """Accumulated record of everything a pipeline run did."""

    source: str
    kind: MediaKind
    stages: dict[str, StageResult] = field(default_factory=dict)

    def record(self, result: StageResult) -> StageResult:
        self.stages[result.stage.value] = result
        return result

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.stages.values())

    @property
    def summary(self) -> str:
        kind = self.kind.value if isinstance(self.kind, MediaKind) else self.kind
        parts = [f"{name}={res.status}" for name, res in self.stages.items()]
        return f"[{kind}] {self.source} :: " + ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "kind": self.kind.value if isinstance(self.kind, MediaKind) else self.kind,
            "ok": self.ok,
            "stages": {k: asdict(v) for k, v in self.stages.items()},
        }
