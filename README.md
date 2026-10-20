# Document layer update (0.2)

The document and OCR layers now use native readers, versioned artifacts and
Hugpy-managed OCR. They no longer depend on abstract_ocr or abstract_pdfs.
See [DOCUMENTS.md](DOCUMENTS.md) for current APIs, limits and migration details.
The remaining facade layers retain the architecture documented below.

# media_intelligence — Abstract Intelligence Platform

A unified, layered facade that turns raw media — **PDFs, images, and video** —
into **structured, searchable, SEO-ready data**. It does not reimplement any
engine: it selects the *best* function of each sibling package and exposes it
behind one clean, lazy API, plus an orchestrated pipeline.

```text
Raw Media (PDF / Image / Video / URL)
   │
   ▼
ingest  → extract → structure → enrich → persist → publish
(webtools) (ocr/    (typed     (hugpy)  (FS / DB) (react/
            pdfs/    metadata)                      nginx)
            videos)
```

## Layers → canonical owners

| Layer        | Owner package        | What it does                                   |
|--------------|----------------------|------------------------------------------------|
| `ingest`     | `abstract_webtools`  | scrape pages, download video (yt-dlp/ffmpeg)   |
| `ocr`        | Hugpy HTTP adapter   | managed vision transcription                   |
| `documents`  | document_engine     | native structure, artifacts, page retrieval     |
| `video`      | `abstract_videos`    | registry pipeline: download/frames/transcribe  |
| `transcribe` | `hugpy` (→ `abstract_ocr` fallback) | Whisper speech-to-text          |
| `enrich`     | `hugpy`              | summaries, keywords, vision captioning, SEO    |
| `persist`    | filesystem (DB-pluggable) | typed JSON/JSONB manifests                |
| `publish`    | `abstract_react` + `abstract_nginx` | SEO/OG metadata + static HTML   |

Overlapping capabilities are resolved to **one owner** (Whisper → `hugpy`;
video download → `webtools`; summarize/keywords → `hugpy`).

## Install

`media_intelligence` is *just this `src/` facade* — it contains none of the
engines. Each layer's owner is its own PyPI package, declared as an **optional
extra**, so you install only what you use:

```bash
pip install media_intelligence              # zero third-party deps — facade only
pip install "media_intelligence[ocr,enrich]"  # just those layers
pip install "media_intelligence[all]"       # the full platform
```

The package has **no required third-party dependencies**: importing it is cheap
(~20 ms) and pulls **none** of the backing packages. Each sibling is imported
**lazily**, only when its layer is actually called; a missing one raises a clear
`MissingDependency` naming the extra to install.

Check what's usable in the current environment without importing anything:

```python
import media_intelligence as mi
mi.available()            # {'ingest': True, 'ocr': True, 'publish': False, ...}
mi.available("enrich")    # True / False
```

## Usage

### Direct namespace access

```python
import media_intelligence as mi

text = mi.ocr.image_to_text("page.png")
kw   = mi.enrich.keywords(text)
mi.documents.process_pdf("doc.pdf")
mi.ingest.download_video("https://site.com/v.mp4", download_directory="/data")
```

### Orchestrated pipeline (idempotent + resumable)

```python
from media_intelligence import MediaPipeline

pipe = MediaPipeline("https://site.com/video.mp4", out_root="/data")
pipe.ingest().extract().structure().enrich().persist().publish()
print(pipe.report.summary)
#   ... or simply:
pipe.run()
```

The pipeline autodetects media kind, dispatches each stage accordingly, skips
stages already satisfied (idempotent), and rehydrates from a prior manifest on
re-run (resumable). Results land in `out_root/<media_id>/manifest.json`.

### Persistence (DB-pluggable, two records)

Each item is persisted as **two** records so indexing stays cheap while
aggregation stays simple:

- `manifest.json` — lean index: ids, counts, `text_chars`, summary, keywords,
  SEO, asset pointers. (The JSONB metadata row.)
- `document.json` — canonical content: full `text`, `pages`/segments,
  `transcript`. The single source of truth for search / aggregation / LLM
  datasets — one read per item, no re-stitching of per-owner on-disk files.

```python
store = mi.persist.FileStore("/data")
store.save_manifest(item.media_id, manifest)   # lean index
store.save_document(item.media_id, document)   # full body
doc = store.load_document(item.media_id)        # aggregation reads this

# later, identical interface, JSONB backend:
# store = mi.persist.PgStore(dsn=...)   # planned (abstract_database)
#   -> metadata in JSONB, body text in a full-text-indexed column
```

`MediaPipeline.persist()` writes both. On re-run, the body is rehydrated from
`document.json`, so `extract`/`enrich` skip (no re-OCR / re-transcribe).
```
