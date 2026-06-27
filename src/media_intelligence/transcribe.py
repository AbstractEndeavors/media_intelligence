"""Extraction layer (audio/video) — speech-to-text.

Canonical owner: ``hugpy`` (the latest ML namespace), via ``whisper_transcribe``
/ ``transcribe_file``. If hugpy is unavailable we fall back to the local Whisper
implementation that ships inside ``abstract_ocr.audio_utils`` — same capability,
different home — so transcription degrades gracefully rather than failing hard.
"""
from __future__ import annotations

from typing import Any

from ._lazy import MissingDependency, require, soft_import

_LAYER = "transcribe"

__all__ = ["transcribe", "transcribe_url"]


def transcribe(audio_or_video_path: str, **kwargs: Any) -> Any:
    """Transcribe a local audio/video file → whisper-style result.

    Prefers ``hugpy``; falls back to ``abstract_ocr`` if hugpy is not installed.
    """
    try:
        fn = require("hugpy", "whisper_transcribe", layer=_LAYER)
        return fn(audio_path=audio_or_video_path, **kwargs)
    except MissingDependency:
        fn = require(
            "abstract_ocr", "transcribe_with_whisper_local", layer=_LAYER
        )
        return fn(audio_or_video_path, **kwargs)


def transcribe_url(url: str, **kwargs: Any):
    """Stream a transcription directly from a media URL (hugpy)."""
    fn = require("hugpy", "whisper_transcribe_url_stream", layer=_LAYER)
    return fn(url, **kwargs)
