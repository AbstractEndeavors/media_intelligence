"""Enrichment layer — content understanding.

Canonical owner: ``hugpy`` (the latest ML/NLP namespace, its own project). One
seam for summarization, keyword extraction/refinement, image captioning (vision),
and the higher-level ``analyze*`` helpers that produce SEO-ready metadata.
"""
from __future__ import annotations

from typing import Any, Optional

from ._lazy import require

_PKG = "hugpy"
_LAYER = "enrich"

__all__ = [
    "summarize",
    "summarize_image",
    "keywords",
    "refine_keywords",
    "keyword_density",
    "caption",
    "analyze",
    "analyze_pdf",
    "analyze_video",
    "execute",
]


def summarize(text: Optional[str] = None, **kwargs: Any) -> str:
    """Abstractive summary of ``text`` (chunked + consolidated)."""
    fn = require(_PKG, "summarize", layer=_LAYER)
    return fn(text, **kwargs) if text is not None else fn(**kwargs)


def summarize_image(image_path: str, **kwargs: Any) -> str:
    """Summarize/describe an image (vision model)."""
    fn = require(_PKG, "summarize_image", layer=_LAYER)
    return fn(image_path, **kwargs)


def keywords(text: str, **kwargs: Any):
    """Extract keyphrases (KeyBERT + spaCy) → list[(phrase, score)]."""
    fn = require(_PKG, "extract_keywords", layer=_LAYER)
    return fn(text, **kwargs)


def refine_keywords(text: str, **kwargs: Any):
    """SEO-refined, density-filtered keywords → ``RefinedResult``."""
    fn = require(_PKG, "refine_keywords", layer=_LAYER)
    return fn(text, **kwargs)


def keyword_density(text: str, kws: Any) -> dict:
    """Keyword density map for ``text`` against ``kws``."""
    fn = require(_PKG, "keyword_density", layer=_LAYER)
    return fn(text, kws)


def caption(image_path: str, prompt: str = "please describe this image", **kwargs: Any) -> str:
    """Caption / visually analyse an image via the cached vision coder."""
    get_vision_coder = require(_PKG, "get_vision_coder", layer=_LAYER)
    coder = get_vision_coder(**{k: v for k, v in kwargs.items() if k in
                                {"model_key", "torch_dtype", "max_tokens", "min_tokens"}})
    analyze_kwargs = {k: v for k, v in kwargs.items() if k in {"max_new_tokens", "max_tokens"}}
    return coder.analyze_image(image_path, prompt=prompt, **analyze_kwargs)


def analyze(text: str, **kwargs: Any):
    """Full text analysis → summary + keywords + metadata bundle."""
    fn = require(_PKG, "analyze", layer=_LAYER)
    return fn(text, **kwargs)


def analyze_pdf(pdf_path: str, **kwargs: Any):
    """Analyze an already-extracted PDF's text into SEO/metadata."""
    fn = require(_PKG, "analyze_pdf", layer=_LAYER)
    return fn(pdf_path, **kwargs)


def analyze_video(*args: Any, **kwargs: Any):
    """Frame-by-frame video understanding (vision over extracted frames)."""
    fn = require(_PKG, "analyze_video", layer=_LAYER)
    return fn(*args, **kwargs)


def execute(*args: Any, **kwargs: Any):
    """Escape hatch: hugpy's unified dispatch (``execute_prompt``).

    Routes any ``(framework, task)`` — chat, vision, ASR, summarize, embed,
    image-gen, keywords — through the model registry.
    """
    fn = require(_PKG, "execute_prompt", layer=_LAYER)
    return fn(*args, **kwargs)
