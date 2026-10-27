"""OCR adapter to Hugpy's managed model API. Never loads model frameworks here."""

from __future__ import annotations

from ..imports.constants import PROMPT
import base64, json, os, urllib.request, urllib.error
from .model import OCRResult




def repetition_suspect(text: str) -> bool:
    """Flag decoder loops for review; repeated source text is retained as evidence."""
    from collections import Counter

    words = text.casefold().split()
    if len(words) < 36:
        return False
    shingles = Counter(tuple(words[i : i + 12]) for i in range(len(words) - 11))
    return any(count >= 3 for count in shingles.values())


class HugpyOCR:
    def __init__(self, *, base_url=None, model=None, api_key=None, max_tokens=None):
        self.base_url = (
            base_url or os.environ.get("HUGPY_CORE_URL") or "http://127.0.0.1:7020"
        ).rstrip("/")
        self.model = (
            model
            or os.environ.get("HUGPY_DOCUMENT_OCR_MODEL")
            or os.environ.get("HUGPY_MEDIA_VISION_MODEL")
        )
        self.api_key = api_key or os.environ.get("HUGPY_DOCUMENT_OCR_API_KEY")
        self.max_tokens = int(
            max_tokens or os.environ.get("HUGPY_DOCUMENT_OCR_MAX_TOKENS", "4096")
        )
        import hashlib

        self.identity = (
            "hugpy-vision:"
            + str(self.model or "unconfigured")
            + ":"
            + str(self.max_tokens)
            + ":"
            + hashlib.sha256(self.base_url.encode()).hexdigest()[:12]
            + ":prompt="
            + hashlib.sha256(PROMPT.encode()).hexdigest()[:16]
        )

    def recognize(self, image: bytes, mime: str, *, timeout: float) -> OCRResult:
        if timeout <= 0:
            raise TimeoutError("Document processing deadline reached before OCR")
        if not self.model:
            raise RuntimeError(
                "OCR needs a configured Hugpy vision model (HUGPY_DOCUMENT_OCR_MODEL)"
            )
        body = {
            "model": self.model,
            "stream": False,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:"
                                + mime
                                + ";base64,"
                                + base64.b64encode(image).decode()
                            },
                        },
                    ],
                }
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(
                req, timeout=max(1, min(timeout, 180))
            ) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Hugpy OCR request failed with HTTP {exc.code}"
            ) from exc
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("Hugpy OCR returned no result")
        choice = choices[0]
        text = (choice.get("message") or {}).get("content")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Hugpy OCR returned no readable text")
        warnings = []
        truncated = choice.get("finish_reason") == "length"
        if truncated:
            warnings.append("OCR stopped at its output limit; this page is incomplete")
        if "[unreadable]" in text.lower():
            warnings.append("OCR marked unreadable content on this page")
        if repetition_suspect(text):
            warnings.append(
                "OCR contains repeated passages that may be a decoder loop; review against the source"
            )
        return OCRResult(
            text.strip(), "hugpy-vision:" + self.model, truncated, warnings
        )
