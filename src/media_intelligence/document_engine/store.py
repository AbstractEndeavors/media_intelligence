"""Atomic artifact persistence keyed by content, source scope and extraction options."""

from __future__ import annotations
import hashlib, json, os, re, tempfile, threading
from pathlib import Path
from contextlib import contextmanager
from .model import Document, Page, ENGINE_VERSION, SCHEMA_VERSION

# A bounded set of locks avoids retaining one lock per uploaded document forever.
_LOCKS = [threading.RLock() for _ in range(64)]


def identity(source: Path, digest: str, options: dict) -> str:
    data = [str(source.resolve()), digest, ENGINE_VERSION, options]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, key: str) -> Path:
        if not re.fullmatch("[0-9a-f]{64}", key):
            raise ValueError("invalid document artifact id")
        return self.root / key[:2] / (key + ".json")

    @contextmanager
    def lock(self, key):
        with _LOCKS[int(key[:8], 16) % len(_LOCKS)]:
            # Cross-process lock; workers and HTTP processes can share the store.
            import fcntl

            path = self.path(key)
            path.parent.mkdir(exist_ok=True, mode=0o700)
            lock = path.with_suffix(".lock")
            fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
            with os.fdopen(fd, "a") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def load(self, key: str) -> Document | None:
        try:
            data = json.loads(self.path(key).read_text())
            if (
                data.get("schema_version") != SCHEMA_VERSION
                or data.get("engine_version") != ENGINE_VERSION
            ):
                return None
            data["pages"] = [Page(**p) for p in data.get("pages", [])]
            return Document(**data)
        except (OSError, ValueError, TypeError):
            return None

    def save(self, doc: Document):
        from dataclasses import asdict

        path = self.path(doc.artifact_id)
        path.parent.mkdir(exist_ok=True, mode=0o700)
        fd, tmp = tempfile.mkstemp(prefix=".document-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(asdict(doc), f, ensure_ascii=False, default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
