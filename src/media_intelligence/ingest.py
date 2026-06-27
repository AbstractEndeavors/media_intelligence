"""Ingestion layer — bring raw media in from the web.

Canonical owner: ``abstract_webtools``. This is the single seam for *acquiring*
media: scraping/parsing a page and downloading video (yt-dlp + ffmpeg). The
``abstract_videos`` package also downloads video, but for the platform we make
webtools the one owner of "fetch from a URL" and let the video pipeline consume
the local file.
"""
from __future__ import annotations

from typing import Any, Optional

from ._lazy import require, soft_import

_PKG = "abstract_webtools"
_LAYER = "ingest"

__all__ = [
    "scrape",
    "soup",
    "page_text",
    "links",
    "download_video",
    "video_info",
    "video_id",
]


def scrape(url: str, **kwargs: Any):
    """Return a ``UnifiedWebManager`` for ``url`` (lazy ``.soup``/``.link_mgr``/...)."""
    UnifiedWebManager = require(_PKG, "UnifiedWebManager", layer=_LAYER)
    return UnifiedWebManager(url=url, **kwargs)


def soup(url: str, **kwargs: Any):
    """Return a parsed BeautifulSoup-backed soup manager for ``url``."""
    get_soup = require(_PKG, "get_soup", layer=_LAYER)
    return get_soup(url, **kwargs)


def page_text(url: str) -> str:
    """Return the visible text of a page."""
    get_soup_text = require(_PKG, "get_soup_text", layer=_LAYER)
    return get_soup_text(url)


def links(url: str, **kwargs: Any):
    """Discover links/images on a page via the link manager."""
    mgr = scrape(url, **kwargs)
    return mgr.link_mgr


def download_video(
    url: str,
    download_directory: Optional[str] = None,
    *,
    cookies_from_browser: Optional[Any] = None,
    cookiefile: Optional[str] = None,
    resilient: bool = True,
    ydl_opts: Optional[dict] = None,
    **kwargs: Any,
):
    """Download a video from ``url`` (yt-dlp) and return the manager.

    The manager exposes the resolved local path(s) and metadata.

    By default (``resilient=True``) this applies robust yt-dlp options that the
    underlying ``abstract_webtools`` downloader does not set on its own:

    * **Native HLS/DASH downloader** instead of the forced ``external_downloader:
      ffmpeg``. Handing the whole stream to ffmpeg is brittle for sites like
      Facebook/Instagram, whose signed fragment URLs expire or 403 mid-download
      and make ffmpeg exit non-zero (e.g. ``ffmpeg exited with code 243``). The
      native downloader retries/refreshes fragments.
    * **Fragment retries** and concurrent fragment downloads.

    For login-gated content (most Facebook reels), pass cookies::

        download_video(url, cookies_from_browser="firefox")
        download_video(url, cookiefile="/path/cookies.txt")

    Anything you put in ``ydl_opts`` wins over these defaults, so you stay in
    full control (e.g. ``ydl_opts={"external_downloader": "ffmpeg"}`` to opt back).
    """
    get_video_mgr = require(_PKG, "get_video_mgr", layer=_LAYER)

    opts: dict[str, Any] = dict(ydl_opts or {})
    if resilient:
        # None => yt-dlp uses its native (resilient) downloader per protocol.
        opts.setdefault("external_downloader", None)
        opts.setdefault("retries", 10)
        opts.setdefault("fragment_retries", 10)
        opts.setdefault("concurrent_fragment_downloads", 4)
    if cookies_from_browser is not None:
        spec = (cookies_from_browser,) if isinstance(cookies_from_browser, str) \
            else tuple(cookies_from_browser)
        opts.setdefault("cookiesfrombrowser", spec)
    if cookiefile is not None:
        opts.setdefault("cookiefile", cookiefile)

    if download_directory is not None:
        kwargs.setdefault("download_directory", download_directory)
    kwargs.setdefault("download_video", True)
    return get_video_mgr(url, ydl_opts=opts, **kwargs)


def video_info(url: str, **kwargs: Any) -> dict:
    """Resolve video metadata for ``url`` without downloading."""
    get_video_info = require(_PKG, "get_video_info", layer=_LAYER)
    return get_video_info(url, **kwargs)


def video_id(url: str) -> str:
    """Return a stable video id for ``url``."""
    get_video_id = require(_PKG, "get_video_id", layer=_LAYER)
    return get_video_id(url)
