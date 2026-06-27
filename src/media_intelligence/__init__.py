"""media_intelligence — the Abstract Intelligence Platform facade.

A unified, layered access layer that turns raw media (PDFs, images, video) into
structured, searchable, SEO-ready data. It does not reimplement any engine; it
selects the *best* function of each sibling package and exposes it behind one
clean, lazy API.

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
    ocr       -> abstract_ocr        (layout-aware multi-engine OCR)
    documents -> abstract_pdfs       (PDF decomposition + HTML)
    video     -> abstract_videos     (registry pipeline: download/frames/SEO)
    transcribe-> hugpy               (Whisper ASR; abstract_ocr fallback)
    enrich    -> hugpy               (summaries, keywords, vision, SEO)
    persist   -> filesystem now, DB-pluggable interface
    publish   -> abstract_react + abstract_nginx (SEO/OG + static HTML)

Every backing package is imported lazily, so ``import media_intelligence`` is
cheap and a missing optional package only errors when that layer is used.
"""
from __future__ import annotations

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

__version__ = "0.1.0"

# Submodules exposed as lazy namespaces via module __getattr__ below.
_LAZY_SUBMODULES = {
    "ingest",
    "ocr",
    "documents",
    "video",
    "transcribe",
    "enrich",
    "structure",
    "persist",
    "publish",
}

# Which backing package(s) each layer needs. ``persist`` is pure-stdlib (always
# available); ``transcribe`` works if either hugpy or abstract_ocr is present.
_LAYER_PACKAGES = {
    "ingest": ("abstract_webtools",),
    "ocr": ("abstract_ocr",),
    "documents": ("abstract_pdfs",),
    "video": ("abstract_videos",),
    "transcribe": ("hugpy", "abstract_ocr"),   # any-of
    "enrich": ("hugpy",),
    "structure": (),
    "persist": (),
    "publish": ("abstract_react",),            # nginx HTML is an additional option
}

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
    def _ok(needed: tuple) -> bool:
        return True if not needed else any(_installed(p) for p in needed)

    if layer is not None:
        if layer not in _LAYER_PACKAGES:
            raise ValueError(f"unknown layer {layer!r}; choose from {sorted(_LAYER_PACKAGES)}")
        return _ok(_LAYER_PACKAGES[layer])
    return {name: _ok(pkgs) for name, pkgs in _LAYER_PACKAGES.items()}

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
