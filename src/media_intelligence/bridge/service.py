"""media_intelligence HTTP bridge — the medium between a UI and hugpy.

The chat UI (and any other front-end) should not reach *past* a bridge straight
into hugpy's per-task `/ml/*` endpoints and re-derive what to do. This module is
that missing bridge: one call runs the `MediaPipeline` (ingest → extract →
structure → enrich) and returns a single typed **DocumentIntelligence** record.

It mirrors the TS `DocumentIntelligence` shape the chat renders, so the same
contract is served whether the UI orchestrates `/ml/*` itself or POSTs here.

Two surfaces:

* `analyze(source, kind=None)` — pure function, returns the record as a dict.
* `build_blueprint(...)` / `create_app()` — optional Flask wrapper exposing
  ``POST /media/analyze``. Flask is an optional dependency (the ``[bridge]`` extra).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

# NOTE: imports are kept deliberately lazy. `..schemas` is pure-stdlib (cheap), but
# `..pipeline` (and through it the abstract_* engines, all themselves lazy) is NOT
# imported until `analyze()` actually runs — so mounting the blueprint at app boot
# costs nothing. The abstract_* deps load only when a real request is processed.
from ..schemas import MediaKind, Stage

__all__ = ["analyze", "document_intelligence", "build_blueprint", "create_app"]

# Only the extract+enrich stages are needed for an interactive "what is this file"
# analysis; persist/publish are skipped (the UI just wants the record back).
_ANALYZE_STAGES = [Stage.INGEST, Stage.EXTRACT, Stage.STRUCTURE, Stage.ENRICH]

# UI MediaCategory -> our MediaKind (document has no distinct kind; treat as PDF).
_KIND_MAP = {
    "pdf": MediaKind.PDF,
    "document": MediaKind.DOCUMENT,
    "image": MediaKind.IMAGE,
    "video": MediaKind.VIDEO,
    "audio": MediaKind.AUDIO,
    "url": MediaKind.URL,
}


def document_intelligence(item: Any, report: Any) -> dict[str, Any]:
    """Project a finished `MediaItem` + `PipelineReport` into the UI record shape."""
    kind = item.kind.value if isinstance(item.kind, MediaKind) else item.kind
    return {
        "source": item.source,
        "kind": kind,
        "text": item.text,
        "pages": item.pages or None,
        "transcript": item.transcript,
        "summary": item.summary,
        "keywords": item.keywords or None,
        "caption": item.metadata.get("caption"),
        "stages": [
            {
                "stage": s.stage.value,
                "status": s.status,
                "detail": s.error or s.detail or None,
                "error": s.error,
            }
            for s in report.stages.values()
        ],
        "ok": report.ok,
    }


def analyze(
    source: str,
    kind: Optional[str] = None,
    *,
    out_root: Optional[str] = None,
) -> dict[str, Any]:
    """Run the media-intelligence pipeline on ``source`` → DocumentIntelligence dict.

    Best-effort: stage failures are recorded in the result's ``stages`` (the
    pipeline runs with ``on_error="record"``), never raised — the caller always
    gets a renderable record.
    """
    # Lazy: only now do we pull in the pipeline (and, on demand, the abstract_* engines).
    from ..pipeline import MediaPipeline

    pipe = MediaPipeline(source, out_root=out_root, on_error="record")
    mapped = _KIND_MAP.get((kind or "").lower())
    if mapped is not None:
        pipe.kind = mapped
        pipe.item.kind = mapped
    pipe.run(stages=_ANALYZE_STAGES)
    return document_intelligence(pipe.item, pipe.report)


def _require_flask():
    try:
        import flask  # noqa: F401

        return flask
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "The media_intelligence HTTP bridge needs Flask. Install it with:  "
            'pip install "media_intelligence[bridge]"'
        ) from exc


def build_blueprint(
    *,
    resolve_file: Optional[Callable[[str], Optional[str]]] = None,
    out_root: Optional[str] = None,
    url_prefix: str = "",
):
    """Build a Flask blueprint exposing ``POST {url_prefix}/media/analyze``.

    Request JSON: ``{"path"|"url"|"source": str}`` or ``{"file": <handle>}``. When
    a ``file`` handle (e.g. a hugpy upload id) is sent, ``resolve_file(handle)``
    must map it to a local path/URL — inject that resolver for your environment
    (it's the one host-specific seam). Mount into hugpy's flask_app, or run
    standalone via :func:`create_app`.

    Response: ``{"ok": true, "result": <DocumentIntelligence>}`` (matches what the
    chat bridge expects), or ``{"ok": false, "error": str}`` with a 4xx/5xx code.
    """
    flask = _require_flask()
    from flask import Blueprint, jsonify, request

    bp = Blueprint("media_intelligence_bridge", __name__, url_prefix=url_prefix or None)

    @bp.post("/media/analyze")
    def _analyze():  # type: ignore[unused-ignore]
        payload = request.get_json(silent=True) or {}
        source = payload.get("path") or payload.get("url") or payload.get("source")
        handle = payload.get("file")
        if handle and resolve_file is not None:
            source = resolve_file(handle) or source
        elif handle and not source:
            source = handle  # assume the handle is already a path
        if not source:
            return jsonify({"ok": False, "error": "no source (path/url/file)"}), 400
        try:
            result = analyze(str(source), kind=payload.get("kind"), out_root=out_root)
            return jsonify({"ok": True, "result": result})
        except Exception as exc:  # noqa: BLE001 — report, don't 500-silently
            return jsonify({"ok": False, "error": str(exc)}), 500

    return bp


def create_app(**blueprint_kwargs: Any):
    """Standalone Flask app hosting the bridge (``python -m media_intelligence.bridge``)."""
    flask = _require_flask()
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(build_blueprint(**blueprint_kwargs))
    return app
