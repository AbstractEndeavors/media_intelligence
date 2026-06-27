"""MediaPipeline — the orchestrated, idempotent, resumable end-to-end pipeline.

Implements the six layers of the vision doc over one typed :class:`MediaItem`::

    ingest -> extract -> structure -> enrich -> persist -> publish

Design properties (vision principles #1 and #3):

* **Layered / decoupled** — each stage is a method that reads and writes the
  shared ``MediaItem``; stages don't call each other.
* **Idempotent** — a stage that already produced its artifact is a no-op
  (recorded as ``skipped``). Safe to re-run.
* **Resumable** — if a manifest already exists in the store, the item is
  rehydrated at construction so a re-run continues where it stopped.
* **Multimodal** — the same six methods serve PDFs, images, audio and video;
  each stage dispatches on :class:`MediaKind` and skips what doesn't apply.

Two call styles::

    MediaPipeline("doc.pdf", out_root="/data").run()

    pipe = MediaPipeline("https://x.com/v.mp4", out_root="/data")
    pipe.ingest().extract().structure().enrich().persist().publish()
    print(pipe.report.summary)
"""
from __future__ import annotations

import os
from typing import Any, Optional

from . import documents, enrich as _enrich, ingest as _ingest, ocr as _ocr
from . import structure as _structure, transcribe as _transcribe, video as _video
from . import publish as _publish
from ._lazy import MediaIntelligenceError, MissingDependency
from .persist import FileStore
from .persist.base import Store
from .schemas import (
    MediaItem,
    MediaKind,
    PipelineReport,
    Stage,
    StageResult,
    detect_media_kind,
)

__all__ = ["MediaPipeline"]

_STAGE_ORDER = [
    Stage.INGEST,
    Stage.EXTRACT,
    Stage.STRUCTURE,
    Stage.ENRICH,
    Stage.PERSIST,
    Stage.PUBLISH,
]


class MediaPipeline:
    """Coordinate the layered media-intelligence pipeline for one source."""

    def __init__(
        self,
        source: str,
        *,
        out_root: Optional[str] = None,
        store: Optional[Store] = None,
        media_id: Optional[str] = None,
        on_error: str = "raise",       # "raise" | "record"
        resume: bool = True,
    ) -> None:
        self.source = source
        self.kind = detect_media_kind(source)
        self.on_error = on_error
        self.out_root = out_root or os.path.join(os.getcwd(), "media_intelligence_out")
        self.store: Store = store or FileStore(self.out_root)
        self.item = MediaItem(source=source, kind=self.kind, media_id=media_id)
        self.report = PipelineReport(source=source, kind=self.kind)

        # Local file? we already know the path.
        if self.kind != MediaKind.URL and os.path.exists(source):
            self.item.local_path = os.path.abspath(source)
        if self.item.media_id is None:
            self.item.media_id = self._default_media_id()

        if resume:
            self._rehydrate()

    # -- helpers ------------------------------------------------------------

    def _default_media_id(self) -> str:
        base = os.path.basename(str(self.source).split("?", 1)[0].rstrip("/"))
        stem, _ = os.path.splitext(base)
        return stem or "media"

    def _rehydrate(self) -> None:
        """Resume: load the prior document (full body) + manifest into the item.

        Restoring ``text``/``pages``/``transcript`` from the document record means
        ``extract``/``structure``/``enrich`` all see their artifacts as already
        satisfied and skip — so a re-run is cheap and never re-OCRs/re-transcribes.
        """
        try:
            if not self.store.exists(self.item.media_id):
                return
            record = self.store.load_document(self.item.media_id)
            if record is None:
                record = self.store.load_manifest(self.item.media_id) or {}
            self.item.title = record.get("title") or self.item.title
            self.item.summary = record.get("summary") or self.item.summary
            self.item.keywords = record.get("keywords") or self.item.keywords
            self.item.seo = record.get("seo") or self.item.seo
            self.item.metadata = record.get("metadata") or self.item.metadata
            self.item.local_path = record.get("local_path") or self.item.local_path
            # full body (present only in the document record)
            self.item.text = record.get("text") or self.item.text
            self.item.pages = record.get("pages") or self.item.pages
            self.item.transcript = record.get("transcript") or self.item.transcript
            self.item.frames = record.get("frames") or self.item.frames
            self.item.manifest_path = self.store.collection_dir(self.item.media_id)
        except Exception:
            # Resume is best-effort; a bad/old record must never block a run.
            pass

    def _run_stage(self, stage: Stage, fn, *, already_done: bool) -> "MediaPipeline":
        if already_done:
            self.report.record(StageResult(stage, "skipped", "already satisfied"))
            return self
        try:
            detail = fn() or ""
            self.report.record(StageResult(stage, "ok", str(detail)))
        except MediaIntelligenceError as exc:
            self.report.record(StageResult(stage, "error", "", error=str(exc)))
            if self.on_error == "raise":
                raise
        except Exception as exc:  # noqa: BLE001 — surface as a recorded stage error
            self.report.record(StageResult(stage, "error", "", error=repr(exc)))
            if self.on_error == "raise":
                raise
        return self

    # -- stages -------------------------------------------------------------

    def ingest(self) -> "MediaPipeline":
        """Bring the media local. Downloads remote video; no-op for local files."""
        done = bool(self.item.local_path)

        def _do() -> str:
            if self.kind in (MediaKind.URL, MediaKind.VIDEO) and not self.item.local_path:
                coll = self.store.collection_dir(self.item.media_id)
                mgr = _ingest.download_video(self.source, download_directory=coll)
                # managers expose the resolved path under a few possible names
                path = (
                    getattr(mgr, "video_path", None)
                    or getattr(mgr, "file_path", None)
                    or getattr(mgr, "output_path", None)
                )
                self.item.local_path = path or coll
                return f"downloaded -> {self.item.local_path}"
            self.item.local_path = os.path.abspath(self.source)
            return f"local -> {self.item.local_path}"

        return self._run_stage(Stage.INGEST, _do, already_done=done)

    def extract(self) -> "MediaPipeline":
        """OCR / transcribe / decompose, dispatching on media kind."""
        done = bool(self.item.text or self.item.transcript or self.item.metadata.get("pdf_result"))

        def _do() -> str:
            path = self.item.local_path or self.source
            if self.kind == MediaKind.IMAGE:
                self.item.text = _ocr.image_to_text(path)
                return "ocr image"
            if self.kind == MediaKind.AUDIO:
                self.item.transcript = _transcribe.transcribe(path)
                return "transcribed audio"
            if self.kind in (MediaKind.VIDEO, MediaKind.URL):
                # The video package owns the idempotent download/frames/transcribe
                # /SEO chain; capture its accumulated info_data.
                info = _video.get_all(
                    url=self.source if self.kind == MediaKind.URL else None,
                    video_path=path if self.kind == MediaKind.VIDEO else None,
                )
                self.item.metadata["video_info"] = info
                self.item.transcript = info.get("whisper") or info.get("transcription") or self.item.transcript
                self.item.summary = info.get("summary") or self.item.summary
                self.item.keywords = info.get("keywords") or self.item.keywords
                self.item.title = info.get("title") or self.item.title
                self.item.seo = info.get("seo") or info.get("seodata") or self.item.seo
                return "video pipeline (get_all)"
            if self.kind == MediaKind.PDF:
                self.item.metadata["pdf_result"] = documents.process_pdf(path)
                # Read back the per-page OCR'd text so the document record holds
                # the full body (source of truth), not just process_pdf's counts.
                pages, full_text = documents.pdf_pages(path)
                if pages:
                    self.item.pages = pages
                    self.item.text = full_text or self.item.text
                return f"pdf decomposition ({len(pages)} page(s))"
            raise MediaIntelligenceError(f"Don't know how to extract kind={self.kind}")

        return self._run_stage(Stage.EXTRACT, _do, already_done=done)

    def structure(self) -> "MediaPipeline":
        """Normalize extraction outputs into the typed page/segment model."""
        done = bool(self.item.pages) and bool(self.item.text)

        def _do() -> str:
            _structure.structure_item(self.item)
            return f"{len(self.item.pages)} segment(s)"

        return self._run_stage(Stage.STRUCTURE, _do, already_done=done)

    def enrich(self) -> "MediaPipeline":
        """Summary + keywords. Skipped if an upstream owner already enriched."""
        done = bool(self.item.summary and self.item.keywords)

        def _do() -> str:
            text = self.item.text
            if not text:
                return "no text to enrich"
            if not self.item.summary:
                self.item.summary = _enrich.summarize(text)
            if not self.item.keywords:
                self.item.keywords = _enrich.keywords(text)
            return "summarized + keyworded"

        return self._run_stage(Stage.ENRICH, _do, already_done=done)

    def persist(self) -> "MediaPipeline":
        """Write both records: the lean manifest (index) and the full document.

        The document holds the canonical text/pages/transcript so downstream
        aggregation, search and LLM-dataset jobs read one record per item instead
        of re-stitching per-owner on-disk files.
        """
        def _do() -> str:
            manifest = _structure.build_manifest(self.item)
            document = _structure.build_document(self.item)
            self.item.manifest_path = self.store.save_manifest(self.item.media_id, manifest)
            doc_path = self.store.save_document(self.item.media_id, document)
            return f"manifest + document -> {doc_path}"

        # persistence is always re-run (cheap, captures latest state)
        return self._run_stage(Stage.PERSIST, _do, already_done=False)

    def publish(self) -> "MediaPipeline":
        """Produce SEO/Open-Graph metadata (best effort; HTML is opt-in).

        Publish backends (react/nginx) are optional: if none is installed the
        stage is recorded as ``skipped`` rather than failing the run.
        """
        if self.item.published:
            self.report.record(StageResult(Stage.PUBLISH, "skipped", "already satisfied"))
            return self

        manifest = _structure.build_manifest(self.item)
        try:
            meta = _publish.seo_metadata(manifest)
        except MissingDependency:
            self.report.record(StageResult(Stage.PUBLISH, "skipped", "publish backend not installed"))
            return self
        except Exception as exc:  # noqa: BLE001
            self.report.record(StageResult(Stage.PUBLISH, "error", "", error=repr(exc)))
            if self.on_error == "raise":
                raise
            return self
        self.item.seo = {**self.item.seo, **(meta or {})}
        self.item.published["seo"] = "generated"
        self.report.record(StageResult(Stage.PUBLISH, "ok", "seo metadata"))
        return self

    # -- driver -------------------------------------------------------------

    def run(self, *, stages: Optional[list[Stage]] = None) -> "MediaPipeline":
        """Run the full pipeline (or a subset) in order, returning self."""
        for stage in (stages or _STAGE_ORDER):
            getattr(self, stage.value)()
        return self

    def __repr__(self) -> str:
        return f"MediaPipeline(source={self.source!r}, kind={self.kind.value}, media_id={self.item.media_id!r})"
