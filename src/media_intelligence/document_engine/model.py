"""Versioned, engine-neutral document artifacts. No model or parser imports."""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Protocol

SCHEMA_VERSION = "hugpy.document.v1"
ENGINE_VERSION = "1.0.0"


@dataclass
class Limits:
    max_bytes: int = 100 * 1024 * 1024
    max_pages: int = 200
    max_chars: int = 2_000_000
    max_ocr_pages: int = 20
    max_cells: int = 200_000
    max_zip_bytes: int = 128 * 1024 * 1024
    deadline_seconds: float = 300


@dataclass
class OCRResult:
    text: str
    method: str
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)


class OCRBackend(Protocol):
    identity: str

    def recognize(self, image: bytes, mime: str, *, timeout: float) -> OCRResult: ...


@dataclass
class Page:
    index: int
    text: str = ""
    status: str = "complete"
    method: str = "native"
    blocks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    width: float | None = None
    height: float | None = None
    name: str | None = None
    needs_review: bool = False
    is_blank: bool = False


@dataclass
class Document:
    artifact_id: str
    source_sha256: str
    name: str
    kind: str
    pages: list[Page] = field(default_factory=list)
    pages_total: int = 0
    status: str = "complete"
    warnings: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    truncated: bool = False
    error: str | None = None
    cache_hit: bool = False
    schema_version: str = SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION

    def payload(self) -> dict[str, Any]:
        d = asdict(self)
        text = "\n\n".join(p.text for p in self.pages if p.text)
        complete = self.status == "complete" and all(
            p.status == "complete" for p in self.pages
        )
        d.update(
            text=text,
            chars=len(text),
            ok=bool(text) and self.status not in ("failed", "cancelled"),
            complete=complete,
            pages_extracted=sum(bool(p.text) for p in self.pages),
            pages_processed=len(self.pages),
            needs_review=any(p.needs_review for p in self.pages),
        )
        d["warnings"] = list(
            dict.fromkeys(
                self.warnings
                + [f"Page {p.index + 1}: {w}" for p in self.pages for w in p.warnings]
            )
        )
        return d


Progress = Callable[[dict[str, Any]], None]
