"""Postgres / JSONB persistence backend — interface-ready stub.

The contract (:class:`media_intelligence.persist.base.Store`) is implemented so
the pipeline can target a database with no code change; the body is intentionally
deferred to a follow-up that wires ``abstract_database``. Constructing it without
that wiring raises a clear, actionable error rather than silently no-op'ing.
"""
from __future__ import annotations

from typing import Any, Optional

from .._lazy import MediaIntelligenceError

__all__ = ["PgStore"]

_NOT_WIRED = (
    "PgStore is the interface-ready stub for the DB/JSONB persistence backend. "
    "v1 ships filesystem persistence (use FileStore); the Postgres/JSONB backend "
    "over 'abstract_database' is the planned next iteration. Track it before "
    "relying on database persistence."
)


class PgStore:
    """Planned JSONB backend. Same :class:`Store` shape as :class:`FileStore`."""

    def __init__(self, dsn: Optional[str] = None, *, table: str = "media_manifests", **_: Any) -> None:
        self.dsn = dsn
        self.table = table
        # Fail loudly at construction so callers don't think persistence happened.
        raise MediaIntelligenceError(_NOT_WIRED)

    # The methods below complete the Protocol for type-checkers / future wiring.
    def save_manifest(self, media_id: str, manifest: dict[str, Any]) -> str:  # pragma: no cover
        raise MediaIntelligenceError(_NOT_WIRED)

    def load_manifest(self, media_id: str) -> Optional[dict[str, Any]]:  # pragma: no cover
        raise MediaIntelligenceError(_NOT_WIRED)

    def save_document(self, media_id: str, document: dict[str, Any]) -> str:  # pragma: no cover
        raise MediaIntelligenceError(_NOT_WIRED)

    def load_document(self, media_id: str) -> Optional[dict[str, Any]]:  # pragma: no cover
        raise MediaIntelligenceError(_NOT_WIRED)

    def exists(self, media_id: str) -> bool:  # pragma: no cover
        raise MediaIntelligenceError(_NOT_WIRED)

    def collection_dir(self, media_id: str) -> str:  # pragma: no cover
        raise MediaIntelligenceError(_NOT_WIRED)
