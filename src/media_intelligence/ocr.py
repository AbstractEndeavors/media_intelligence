"""Extraction layer (images) — OCR.

Canonical owner: ``abstract_ocr``. Multi-engine, layout-aware OCR plus the
per-frame video-OCR helpers. ``abstract_videos`` re-implements a slice of these;
the platform routes everyone through ``abstract_ocr`` so there is one OCR owner.
"""
from __future__ import annotations

from typing import Any, Optional

from ._lazy import require, soft_import

_PKG = "abstract_ocr"
_LAYER = "ocr"

__all__ = [
    "image_to_text",
    "image_to_text_layout",
    "directory_to_texts",
    "video_frames",
    "video_text",
    "best_thumbnail",
]


def image_to_text(image_path: str, preprocess: bool = True) -> str:
    """OCR a single image to text (Paddle-first with Tesseract fallback)."""
    fn = require(_PKG, "convert_image_to_text", layer=_LAYER)
    return fn(image_path, preprocess=preprocess)


def image_to_text_layout(image_path: str, config: Any = None, chain: Optional[list] = None):
    """Run the modern layout-aware OCR pipeline → ``PipelineReport``.

    Reading-order aware, with column detection and region segmentation.
    """
    mod = soft_import(_PKG + ".layout_ocr.pipeline", layer=_LAYER)
    run_on_image = getattr(mod, "run_on_image", None)
    if run_on_image is None:  # fall back to top-level export in some builds
        run_on_image = require(_PKG, "run_on_image", layer=_LAYER)
    return run_on_image(image_path, config=config, chain=chain)


def directory_to_texts(directory: str, **kwargs: Any):
    """Batch-OCR every image in a directory."""
    fn = require(_PKG, "extract_image_texts_from_directory", layer=_LAYER)
    return fn(directory, **kwargs)


def video_frames(video_path: str, directory: str, **kwargs: Any):
    """Sample frames from a video into ``directory``."""
    fn = require(_PKG, "extract_video_frames", layer=_LAYER)
    return fn(video_path, directory, **kwargs)


def video_text(video_path: str, **kwargs: Any):
    """Extract on-screen text across a video's frames."""
    fn = require(_PKG, "analyze_video_text", layer=_LAYER)
    return fn(video_path, **kwargs)


def best_thumbnail(video_text_or_whisper: Any, keywords: Any, directory: str, **kwargs: Any):
    """Pick the most representative thumbnail frame using transcript keywords."""
    fn = require(_PKG, "pick_optimal_thumbnail", layer=_LAYER)
    return fn(video_text_or_whisper, keywords, directory, **kwargs)
