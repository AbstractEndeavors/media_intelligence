"""Native PDF structure and optional worker-managed OCR, page by page."""

from __future__ import annotations
import io, time
from .model import Page


def _lines(words):
    groups = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        row = next(
            (r for r in reversed(groups[-3:]) if abs(r[0]["top"] - w["top"]) < 3), None
        )
        if row is None:
            groups.append([w])
        else:
            row.append(w)
    return [sorted(r, key=lambda w: w["x0"]) for r in groups]


def _columns(words, width):
    """Recover clear page-wide gutters; preserve word geometry for review."""
    intervals = sorted((w["x0"], w["x1"]) for w in words)
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    gaps = [
        (b[0] - a[1], (a[1] + b[0]) / 2)
        for a, b in zip(merged, merged[1:])
        if b[0] - a[1] > width * 0.075
        and width * 0.15 < (a[1] + b[0]) / 2 < width * 0.85
    ]
    # A clear gutter needs words on at least two lines on either side.
    candidates = []
    for _, x in sorted(gaps, reverse=True):
        if (
            len(_lines([w for w in words if w["x1"] <= x])) >= 2
            and len(_lines([w for w in words if w["x0"] >= x])) >= 2
        ):
            candidates.append(x)
    return sorted(candidates[:2])


def _native(page):
    words = page.extract_words()
    blocks = []
    table_boxes = []
    for ti, table in enumerate(page.find_tables()):
        matrix = table.extract()
        if not matrix or not any(any(c for c in row) for row in matrix):
            continue
        bbox = list(table.bbox)
        table_boxes.append(bbox)
        cells = []
        for ri, row in enumerate(table.rows):
            for ci, box in enumerate(row.cells):
                if box is None:
                    continue
                text = (
                    matrix[ri][ci] if ri < len(matrix) and ci < len(matrix[ri]) else ""
                )
                cells.append(
                    {"row": ri, "column": ci, "text": text or "", "bbox": list(box)}
                )
        blocks.append(
            {
                "type": "table",
                "rows": matrix,
                "cells": cells,
                "bbox": bbox,
                "text": "\n".join(" | ".join(c or "" for c in row) for row in matrix),
                "source": {"table": ti},
            }
        )

    def in_table(w):
        x = (w["x0"] + w["x1"]) / 2
        y = (w["top"] + w["bottom"]) / 2
        return any(a <= x <= c and b <= y <= d for a, b, c, d in table_boxes)

    words = [w for w in words if not in_table(w)]
    # Full-width top/bottom lines stay outside a column flow.
    lines = _lines(words)
    furniture = []
    body = []
    for row in lines:
        if row[-1]["x1"] - row[0]["x0"] > page.width * 0.65 and (
            row[0]["top"] < page.height * 0.14 or row[0]["top"] > page.height * 0.9
        ):
            furniture.extend(row)
        else:
            body.extend(row)
    dividers = _columns(body, page.width)
    for kind, group in [("furniture", furniture)] + [
        ("paragraph", [w for w in body if sum(w["x0"] > x for x in dividers) == col])
        for col in range(len(dividers) + 1)
    ]:
        if not group:
            continue
        for row in _lines(group):
            bbox = [
                min(w["x0"] for w in row),
                min(w["top"] for w in row),
                max(w["x1"] for w in row),
                max(w["bottom"] for w in row),
            ]
            blocks.append(
                {
                    "type": kind,
                    "text": " ".join(w["text"] for w in row),
                    "bbox": bbox,
                    "words": [
                        {
                            "text": w["text"],
                            "bbox": [w["x0"], w["top"], w["x1"], w["bottom"]],
                        }
                        for w in row
                    ],
                    "column": sum(bbox[0] > x for x in dividers),
                }
            )

    def key(b):
        if b["type"] == "furniture":
            return (-1 if b["bbox"][1] < page.height / 2 else 99, b["bbox"][1])
        if b["type"] == "table":
            return (sum(b["bbox"][0] > x for x in dividers), b["bbox"][1])
        return (b.get("column", 0), b["bbox"][1])

    blocks.sort(key=key)
    for i, b in enumerate(blocks):
        b["reading_order"] = i
    return blocks, "\n".join(b["text"] for b in blocks if b.get("text")), dividers


def render_page(path, index, *, dpi=150):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        page = pdf[index]
        try:
            scale = min(
                dpi / 72,
                (4_000_000 / max(1, page.get_width() * page.get_height())) ** 0.5,
            )
            bitmap = page.render(scale=scale)
            try:
                image = bitmap.to_pil()
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue()
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        pdf.close()


def pdf_pages(path, limits, backend, mode, deadline, meta, previous):
    import pdfplumber

    used_ocr = 0
    with pdfplumber.open(path) as pdf:
        meta.update(page_count=len(pdf.pages), pagination="page")
        for tag in ("Title", "Author"):
            value = (pdf.metadata or {}).get(tag)
            if isinstance(value, str):
                meta[tag.lower()] = value[:300]
        for index, raw in enumerate(pdf.pages[: limits.max_pages]):
            if time.monotonic() > deadline:
                yield Page(
                    index,
                    status="cancelled",
                    error="Document processing deadline reached",
                )
                break
            prior = previous.get(index)
            if prior and prior.status == "complete":
                raw.close()
                yield prior
                continue
            page = Page(index, width=float(raw.width), height=float(raw.height))
            try:
                page.blocks, page.text, dividers = _native(raw)
                for block in page.blocks:
                    block["source"] = {**block.get("source", {}), "page": index + 1}
                image_area = sum(
                    max(0, i["x1"] - i["x0"]) * max(0, i["bottom"] - i["top"])
                    for i in raw.images
                )
                has_visual_content = bool(raw.images or raw.curves or raw.rects)
                bad_text = (
                    page.text.count("\ufffd") > max(2, len(page.text) * 0.03)
                    or "(cid:" in page.text
                )
                needs_ocr = (
                    mode == "force"
                    or bad_text
                    or (not page.text.strip() and has_visual_content)
                    or (
                        image_area > raw.width * raw.height * 0.6
                        and len(page.text) < 80
                    )
                )
                if not page.text.strip() and not has_visual_content:
                    page.is_blank = True
                if dividers:
                    page.needs_review = True
                    page.warnings.append(
                        "Column reading order was recovered from native geometry; review complex layouts and unruled tables"
                    )
                if needs_ocr:
                    page.status = "needs_ocr"
                    if mode == "off":
                        page.warnings.append(
                            "This page requires OCR; native-only extraction was requested"
                        )
                    elif backend is None:
                        page.warnings.append(
                            "This page requires a configured OCR backend"
                        )
                    elif used_ocr >= limits.max_ocr_pages:
                        page.warnings.append("Document reached its OCR page limit")
                    else:
                        used_ocr += 1
                        result = backend.recognize(
                            render_page(path, index),
                            "image/png",
                            timeout=deadline - time.monotonic(),
                        )
                        if not result.text.strip():
                            raise ValueError("OCR returned no readable text")
                        page.text = result.text
                        page.method = result.method
                        page.needs_review = True
                        # Keep native evidence separate from model interpretation.
                        page.blocks = [
                            {
                                "type": "ocr_markdown",
                                "text": result.text,
                                "source": {"page": index + 1},
                                "bbox": None,
                                "native_blocks": page.blocks,
                                "inferred": True,
                            }
                        ]
                        page.status = (
                            "partial"
                            if result.truncated or result.warnings
                            else "complete"
                        )
                        page.warnings.extend(result.warnings)
                        page.warnings.append(
                            "OCR is model-interpreted text; verify critical values against the original page"
                        )
            except Exception as exc:
                page.status = "partial" if page.text else "failed"
                page.error = " ".join(str(exc).split())[:300]
                page.warnings.append("Page processing failed: " + page.error)
            finally:
                raw.close()
            yield page
