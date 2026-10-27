"""media_intelligence — the Abstract Intelligence Platform facade.

A unified, layered access layer that turns raw media (PDFs, images, video) into
structured, searchable, SEO-ready data. The document layer owns native extraction and artifacts; model inference
uses Hugpy. Other media layers remain lazy adapters.

Two ways to use it
------------------

1. Direct namespace access — grab one tool::

       import media_intelligence as mi
       text  = mi.ocr.image_to_text("page.png")
       kw    = mi.enrich.keywords(text)
       mi.documents.process_pdf("doc.pdf")

2. The orchestrated, idempotent/resumable pipeline::

       from media_intelligence import MediaPipeline
       pipe = MediaPipeline("https://site.com/video.mp4", out_root="/data")
       pipe.ingest().extract().structure().enrich().persist().publish()
       print(pipe.report.summary)
       #  ... or just:  pipe.run()

Layers map one-to-one onto canonical owning packages:

    ingest    -> abstract_webtools   (scrape + yt-dlp video download)
    ocr       -> Hugpy HTTP          (worker-managed model inference)
    documents -> document_engine     (native readers, artifacts, explicit OCR)
    video     -> abstract_videos     (registry pipeline: download/frames/SEO)
    transcribe-> hugpy               (Whisper ASR; abstract_ocr fallback)
    enrich    -> hugpy               (summaries, keywords, vision, SEO)
    persist   -> filesystem now, DB-pluggable interface
    publish   -> abstract_react + abstract_nginx (SEO/OG + static HTML)

Every backing package is imported lazily, so ``import media_intelligence`` is
cheap and a missing optional package only errors when that layer is used.
"""

from __future__ import annotations

from .imports.constants import _LAZY_SUBMODULES, _LAYER_PACKAGES

import importlib
import importlib.util
from typing import TYPE_CHECKING

from ._lazy import MediaIntelligenceError, MissingDependency
from .schemas import (
    MediaItem,
    MediaKind,
    PipelineReport,
    Stage,
    StageResult,
    detect_media_kind,
)

__version__ = "0.2.0"

# Submodules exposed as lazy namespaces via module __getattr__ below.

# Which backing package(s) each layer needs. ``persist`` is pure-stdlib (always
# available); ``transcribe`` works if either hugpy or abstract_ocr is present.

__all__ = [
    "MediaPipeline",
    "MediaItem",
    "MediaKind",
    "Stage",
    "StageResult",
    "PipelineReport",
    "detect_media_kind",
    "available",
    "MediaIntelligenceError",
    "MissingDependency",
    "__version__",
    *sorted(_LAZY_SUBMODULES),
]


def _installed(package: str) -> bool:
    """Whether ``package`` is importable — without importing it."""
    try:
        return importlib.util.find_spec(package) is not None
    except (ImportError, ValueError):
        return False


def available(layer: str | None = None):
    """Report which layers are usable in this environment, without importing them.

    >>> import media_intelligence as mi
    >>> mi.available()            # {'ingest': True, 'ocr': True, 'publish': False, ...}
    >>> mi.available("enrich")    # True / False

    A layer is available if (any of) its backing package(s) are installed. The
    pure-stdlib layers (``structure``, ``persist``) are always available.
    """

    def _ok(name: str, needed: tuple) -> bool:
        return (
            True
            if not needed
            else (all if name == "documents" else any)(_installed(p) for p in needed)
        )

    if layer is not None:
        if layer not in _LAYER_PACKAGES:
            raise ValueError(
                f"unknown layer {layer!r}; choose from {sorted(_LAYER_PACKAGES)}"
            )
        return _ok(layer, _LAYER_PACKAGES[layer])
    return {name: _ok(name, pkgs) for name, pkgs in _LAYER_PACKAGES.items()}


if TYPE_CHECKING:  # for type checkers / IDEs only — no runtime import cost
    from . import (  # noqa: F401
        documents,
        enrich,
        ingest,
        ocr,
        persist,
        publish,
        structure,
        transcribe,
        video,
    )
    from .pipeline import MediaPipeline  # noqa: F401


def __getattr__(name: str):
    """PEP 562 lazy attribute access.

    Keeps the import graph flat: namespaces and the (heavier) pipeline module
    are only imported when first referenced.
    """
    if name == "MediaPipeline":
        module = importlib.import_module(".pipeline", __name__)
        return module.MediaPipeline
    if name in _LAZY_SUBMODULES:
        return importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(__all__) | set(globals()))
