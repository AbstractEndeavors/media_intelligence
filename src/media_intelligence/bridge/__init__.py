"""media_intelligence HTTP bridge.

The medium between a front-end (e.g. the chat UI) and hugpy: one endpoint that
runs the full MediaPipeline and returns a typed DocumentIntelligence record,
instead of the UI reaching past it into hugpy's per-task /ml/* endpoints.

    from media_intelligence.bridge import analyze, build_blueprint, create_app

    analyze("/path/doc.pdf")                 # -> DocumentIntelligence dict
    app = create_app(); app.run(port=8800)   # POST /media/analyze
"""
from __future__ import annotations

from .service import analyze, build_blueprint, create_app, document_intelligence

__all__ = ["analyze", "document_intelligence", "build_blueprint", "create_app"]
