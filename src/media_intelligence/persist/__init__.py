"""Persistence layer — filesystem now, DB-pluggable interface.

::

    store = mi.persist.FileStore("/data")
    store.save_manifest(item.media_id, manifest)
    # later, same interface:
    # store = mi.persist.PgStore(dsn=...)   # JSONB backend (planned)
"""
from __future__ import annotations

from .base import Store
from .filestore import FileStore
from .pgstore import PgStore

__all__ = ["Store", "FileStore", "PgStore"]
