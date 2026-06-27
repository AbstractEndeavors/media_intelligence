"""Persistence interface — one contract, swappable backends.

Vision principle: *local-first, cloud-optional*. v1 ships a filesystem store;
the same interface admits a Postgres/JSONB store later (``abstract_database``)
with no change to the pipeline. Stores are addressed by ``media_id`` and persist
the typed manifest plus a pointer to the on-disk asset collection.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

__all__ = ["Store"]


@runtime_checkable
class Store(Protocol):
    """The persistence contract every backend implements."""

    def save_manifest(self, media_id: str, manifest: dict[str, Any]) -> str:
        """Persist the lean index ``manifest``; return a locator (path/row id)."""
        ...

    def load_manifest(self, media_id: str) -> Optional[dict[str, Any]]:
        """Return the stored manifest for ``media_id`` or ``None``."""
        ...

    def save_document(self, media_id: str, document: dict[str, Any]) -> str:
        """Persist the full content ``document`` (text/pages/transcript)."""
        ...

    def load_document(self, media_id: str) -> Optional[dict[str, Any]]:
        """Return the full content document for ``media_id`` or ``None``."""
        ...

    def exists(self, media_id: str) -> bool:
        """Whether a manifest already exists (drives idempotent resume)."""
        ...

    def collection_dir(self, media_id: str) -> str:
        """Return the directory that holds this item's asset collection."""
        ...
