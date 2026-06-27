"""Output layer — turn structured data into web-ready content.

Two canonical owners:

- ``abstract_react``  — SEO / Open-Graph metadata (and frontend build tooling).
- ``abstract_nginx``  — static HTML (galleries, viewers, SEO index pages),
  nginx config + domain bootstrap.

Both are optional. A missing package raises a clear :class:`MissingDependency`
from the relevant call rather than breaking ``import media_intelligence``.
``abstract_pdfs`` also renders its own viewer/gallery HTML during document
processing, so for PDFs the publish step is frequently already satisfied upstream.
"""
from __future__ import annotations

from typing import Any

from ._lazy import require, soft_import

_REACT = "abstract_react"
_NGINX = "abstract_nginx"
_LAYER = "publish"

__all__ = [
    "seo_metadata",
    "open_graph",
    "title_variants",
    "generate_html",
    "create_seo_files",
    "bootstrap_domain",
]


# --- SEO / metadata (abstract_react) ---------------------------------------

def seo_metadata(info: dict) -> dict:
    """Produce normalized SEO metadata from an info/manifest dict."""
    fn = require(_REACT, "generate_metadata", layer=_LAYER)
    return fn(info)


def open_graph(meta: dict) -> dict:
    """Build Open-Graph output from a metadata dict."""
    fn = require(_REACT, "build_og", layer=_LAYER)
    return fn(meta)


def title_variants(domain: str, **kwargs: Any):
    """Derive title variants from a domain."""
    fn = require(_REACT, "title_variants_from_domain", layer=_LAYER)
    return fn(domain, **kwargs)


# --- static HTML + serving (abstract_nginx) --------------------------------

def generate_html(root: str, base_url: str, media_root: str, site_root: str,
                  *, recurse: bool = False, pdf_path: Any = None) -> Any:
    """Render gallery/viewer/SEO HTML over a structured asset root."""
    gh = soft_import(_NGINX + ".generate_htmls", layer=_LAYER)
    return gh.run(root, base_url, media_root, site_root, recurse, pdf_path)


def create_seo_files(domain: str, root_dir: str) -> Any:
    """Generate SEO index/landing files for a domain."""
    fn = require(_NGINX, "create_seo_files", layer=_LAYER)
    return fn(domain, root_dir)


def bootstrap_domain(root_dir: str, **kwargs: Any) -> Any:
    """Bootstrap a domain directory structure + nginx config."""
    fn = require(_NGINX, "bootstrap_domain", layer=_LAYER)
    return fn(root_dir, **kwargs)
