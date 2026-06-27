"""Lazy / soft import plumbing for the media_intelligence facade.

The whole point of this package is to be a *thin* unified access layer over a
set of heavy sibling packages (paddleocr, torch, yt-dlp, whisper, ...). Importing
``media_intelligence`` must stay cheap, so every sibling package is imported
lazily — at first *use*, never at module import time — and the result is cached.

If an optional layer's backing package is not installed, we raise a single,
actionable :class:`MissingDependency` error that names the extra to install
rather than leaking a raw ``ModuleNotFoundError`` from deep inside a submodule.
"""
from __future__ import annotations

import functools
import importlib
from types import ModuleType
from typing import Any, Callable

__all__ = [
    "MediaIntelligenceError",
    "MissingDependency",
    "soft_import",
    "require",
    "lazy_namespace",
]


class MediaIntelligenceError(RuntimeError):
    """Base error for the media_intelligence facade."""


class MissingDependency(MediaIntelligenceError):
    """A layer was used but its backing package is not installed."""


# Which pip extra installs which backing package — used to build helpful errors.
_EXTRA_FOR_PACKAGE = {
    "abstract_essentials": "(core)",
    "abstract_webtools": "ingest",
    "abstract_ocr": "ocr",
    "abstract_pdfs": "documents",
    "abstract_videos": "video",
    "hugpy": "enrich",
    "abstract_react": "publish",
    "abstract_nginx": "publish",
}

_MODULE_CACHE: dict[str, ModuleType] = {}


def soft_import(package: str, *, layer: str | None = None) -> ModuleType:
    """Import ``package`` lazily, caching the module.

    Raises :class:`MissingDependency` (not ``ModuleNotFoundError``) with an
    install hint if the package is absent.
    """
    cached = _MODULE_CACHE.get(package)
    if cached is not None:
        return cached
    try:
        module = importlib.import_module(package)
    except ModuleNotFoundError as exc:
        # Only translate a *missing backing package*; a genuine sub-import error
        # inside an installed package should surface unchanged.
        if exc.name and (exc.name == package or package.startswith(exc.name + ".")):
            # Resolve the install hint against the *top-level* package, so a
            # missing submodule (e.g. "abstract_nginx.generate_htmls") still
            # points at the right extra.
            top = package.split(".", 1)[0]
            extra = _EXTRA_FOR_PACKAGE.get(top, top)
            hint = f'pip install "media_intelligence[{extra}]"' if extra and extra != "(core)" \
                else f"pip install {top}"
            raise MissingDependency(
                f"The '{layer or package}' layer needs '{package}', which is not "
                f"installed. Install it with:  {hint}"
            ) from exc
        raise
    _MODULE_CACHE[package] = module
    return module


def require(package: str, attr: str, *, layer: str | None = None) -> Any:
    """Return ``attr`` from a soft-imported ``package``.

    Raises a clear error if the package is installed but the symbol is gone
    (e.g. an upstream rename) so failures point at the facade, not the user.
    """
    module = soft_import(package, layer=layer)
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        raise MediaIntelligenceError(
            f"'{package}.{attr}' is not available — the upstream API may have "
            f"changed. The media_intelligence '{layer or package}' layer needs updating."
        ) from exc


def lazy_namespace(loader: Callable[[], ModuleType]) -> Callable[[], ModuleType]:
    """Wrap a submodule loader so the import happens once and is memoised."""
    return functools.lru_cache(maxsize=1)(loader)
