"""Filesystem persistence backend (the v1 default).

Stores each item as ``<root>/<media_id>/manifest.json`` alongside its asset
collection directory. Uses ``abstract_essentials`` JSON helpers when present,
falling back to the stdlib so persistence never hard-depends on anything.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

__all__ = ["FileStore"]


def _safe_dump(data: Any, path: str) -> None:
    try:  # prefer the in-house atomic/normalised writer
        from abstract_essentials import safe_dump_to_json  # type: ignore

        safe_dump_to_json(data=data, file_path=path)
        return
    except Exception:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def _safe_load(path: str) -> Any:
    try:
        from abstract_essentials import safe_load_from_json  # type: ignore

        return safe_load_from_json(path)
    except Exception:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)


class FileStore:
    """Manifest + asset persistence rooted at a directory."""

    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(os.path.expanduser(root))
        os.makedirs(self.root, exist_ok=True)

    def collection_dir(self, media_id: str) -> str:
        d = os.path.join(self.root, self._safe(media_id))
        os.makedirs(d, exist_ok=True)
        return d

    def _manifest_path(self, media_id: str) -> str:
        return os.path.join(self.collection_dir(media_id), "manifest.json")

    def _document_path(self, media_id: str) -> str:
        return os.path.join(self.collection_dir(media_id), "document.json")

    def exists(self, media_id: str) -> bool:
        return os.path.isfile(self._manifest_path(media_id))

    def save_manifest(self, media_id: str, manifest: dict[str, Any]) -> str:
        path = self._manifest_path(media_id)
        _safe_dump(manifest, path)
        return path

    def load_manifest(self, media_id: str) -> Optional[dict[str, Any]]:
        path = self._manifest_path(media_id)
        if not os.path.isfile(path):
            return None
        return _safe_load(path)

    def save_document(self, media_id: str, document: dict[str, Any]) -> str:
        path = self._document_path(media_id)
        _safe_dump(document, path)
        return path

    def load_document(self, media_id: str) -> Optional[dict[str, Any]]:
        path = self._document_path(media_id)
        if not os.path.isfile(path):
            return None
        return _safe_load(path)

    @staticmethod
    def _safe(media_id: str) -> str:
        # keep collection dir names filesystem-safe
        return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in str(media_id))
