"""Orchestration layer (video) — the registry-backed video pipeline.

Canonical owner: ``abstract_videos``. Idempotent, resumable, registry-backed:
``get_all`` walks info → download → thumbnails → transcription → metadata → SEO
and accumulates everything into one ``info_data`` dict.
"""
from __future__ import annotations

from typing import Any, Optional

from ._lazy import require

_PKG = "abstract_videos"
_LAYER = "video"

__all__ = [
    "get_all",
    "info",
    "download",
    "transcription",
    "thumbnails",
    "metadata",
    "seo",
]


def get_all(
    url: Optional[str] = None,
    video_id: Optional[str] = None,
    video_path: Optional[str] = None,
    force_refresh: bool = False,
    **kwargs: Any,
) -> dict:
    """THE whole-video entry point → one accumulated ``info_data`` dict."""
    fn = require(_PKG, "get_all", layer=_LAYER)
    return fn(
        url=url,
        video_id=video_id,
        video_path=video_path,
        force_refresh=force_refresh,
        **kwargs,
    )


def _getter(name: str):
    def call(*args: Any, **kwargs: Any):
        fn = require(_PKG, name, layer=_LAYER)
        return fn(*args, **kwargs)
    call.__name__ = name
    return call


# Individual idempotent artifact getters, surfaced with clean names.
info = _getter("get_video_info")
download = _getter("get_video_download")
transcription = _getter("get_video_transcription")
thumbnails = _getter("get_video_thumbnails")
metadata = _getter("get_video_metadata")
seo = _getter("get_video_seodata")
