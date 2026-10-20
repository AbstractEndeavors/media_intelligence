"""Bounded parser jobs. Only the child process receives resource limits."""

from __future__ import annotations
import json, os, subprocess, sys, threading
from pathlib import Path
from .model import Limits

_SLOTS = threading.BoundedSemaphore(2)


def run_job(
    source,
    *,
    store_root=None,
    ocr="auto",
    refresh=False,
    max_pages=200,
    max_ocr_pages=20,
):
    limits = Limits()
    limits.max_pages = max(1, min(int(max_pages), limits.max_pages))
    limits.max_ocr_pages = max(0, min(int(max_ocr_pages), limits.max_ocr_pages))
    payload = {
        "source": str(source),
        "store_root": str(store_root) if store_root else None,
        "ocr": ocr,
        "refresh": bool(refresh),
        "limits": limits.__dict__,
    }
    env = dict(
        os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1"
    )
    if not _SLOTS.acquire(timeout=5):
        return {
            "ok": False,
            "complete": False,
            "status": "failed",
            "error": "Document workers are busy; retry shortly",
        }
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "media_intelligence.document_engine.job"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=limits.deadline_seconds + 10,
        )
        if proc.returncode != 0:
            return {
                "ok": False,
                "complete": False,
                "status": "failed",
                "error": "Document worker failed or exceeded its resource limit",
            }
        try:
            return json.loads(proc.stdout)
        except ValueError:
            return {
                "ok": False,
                "complete": False,
                "status": "failed",
                "error": "Document worker returned an invalid result",
            }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "complete": False,
            "status": "cancelled",
            "error": "Document processing deadline reached; completed pages are checkpointed for retry",
        }
    finally:
        _SLOTS.release()


def main():
    import resource
    from .service import extract_document

    body = json.load(sys.stdin)
    limits = Limits(**body.pop("limits"))
    memory_mb = int(os.environ.get("HUGPY_DOCUMENT_WORKER_MEMORY_MB", "4096"))
    resource.setrlimit(
        resource.RLIMIT_AS, (memory_mb * 1024 * 1024, memory_mb * 1024 * 1024)
    )
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (int(limits.deadline_seconds), int(limits.deadline_seconds) + 2),
    )
    try:
        result = extract_document(limits=limits, **body)
    except Exception as exc:
        result = {
            "ok": False,
            "complete": False,
            "status": "failed",
            "error": " ".join(str(exc).split())[:400],
        }
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
