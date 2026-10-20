# Shared document extraction

The document capability owns native parsing, structured artifacts and resumable
page processing. It does not import abstract_ocr or abstract_pdfs. Hugpy Media
and Toolserver use this same implementation; the Station harness is not involved.
Other facade layers retain their existing optional adapters.

Install `media_intelligence[documents]`. Importing the facade is still stdlib-only.

```python
from media_intelligence.documents import extract_document, read_page, search_document
result = extract_document("invoice.pdf", store_root="./artifacts", ocr="auto")
page = read_page("invoice.pdf", result["artifact_id"], 1, store_root="./artifacts")
hits = search_document("invoice.pdf", result["artifact_id"], "Total", store_root="./artifacts")
```

Hosted callers should use `run_job`, which isolates parsers in a child process.
The library does not authorize source paths: hosted Media applies its upload-root
jail, and Core applies guest session ownership before forwarding a request.
Page and search requests require the original uploaded source plus artifact ID;
an ID alone does not grant access. Artifacts are bound to canonical source path,
content SHA-256, engine version, OCR backend/model, transcription prompt hash
and extraction options.

## Readers and evidence

- PDF: native words and bounding boxes, ruled tables and cell boxes, page references.
  Clear column gutters are recovered heuristically and flagged for review.
- DOCX: body paragraphs and tables in order, merged cells, section headers/footers,
  footnotes/endnotes. Word has a logical document unit, not invented PDF pagination.
- XLSX/XLSM: worksheets, cell addresses, formulas and cached values. Missing cached
  values preserve the formula and generate a warning; formulas are never evaluated.
- PPTX: slides in presentation relationship order, text and tables in shape order.
- Text, Markdown, JSON, XML, YAML, CSV/TSV: encoding-aware reads and table rows.
  BOM UTF-16/32 is supported; a Windows-1252 fallback is explicitly reported.
- Legacy binary DOC/XLS/PPT returns a conversion requirement.

`complete` reports processing coverage, not transcription accuracy. Every source
page/unit retains its status, method, warnings and errors, including unread pages.
Blank PDF pages are distinct from scans. Document status is `complete`, `partial`,
`failed` or `cancelled`. OCR/layout interpretation sets `needs_review` independently.
Empty OCR and output-limit truncation never complete a page. Suspected repeated
passages are retained but mark the page for review and leave it incomplete. Partial retries reuse
completed PDF pages; changed source contents cannot reuse stale artifacts.

## Managed OCR

`ocr="auto"` reads native content first and routes scans, graphics-only pages or
suspect text layers to Hugpy. `off` performs no inference; `force` requests OCR
for every page within the budget. Set `HUGPY_DOCUMENT_OCR_MODEL` (or existing
`HUGPY_MEDIA_VISION_MODEL`) and `HUGPY_CORE_URL`. Optional
`HUGPY_DOCUMENT_OCR_API_KEY` authenticates the service request. Default OCR output
budget is 4096 tokens, adjustable with `HUGPY_DOCUMENT_OCR_MAX_TOKENS`.

The adapter sends rendered pages to `/v1/chat/completions`. Core/Wrapper owns
model placement and inference. Model text is marked as inferred Markdown; the
artifact retains native evidence separately and never invents OCR bounding boxes.
There is no local Paddle, Tesseract, Docling, Transformers or Torch import here.
A missing/unavailable backend remains a visible page error. No fallback silently
starts a second model runtime.

Default hosted limits: 100 MB source, 200 pages, 20 OCR pages per job, two million
text characters, 200,000 spreadsheet/CSV cells, 128 MB decompressed Office XML,
300-second deadline. A child receives a 4 GB address-space limit and CPU limit;
two child jobs per Media process run at once. Set `HUGPY_DOCUMENT_WORKER_MEMORY_MB`
for a different address-space ceiling. Limits or cancellation preserve checkpoints.
Artifacts use atomic private JSON files under `HUGPY_DOCUMENTS_HOME` (Media defaults
to its uploads root's `.documents`). They require operator retention/backup policy;
removing an uploaded source prevents retrieval even if an artifact remains.

## Integration and migration

Media: `extract`, `document_inspect`, `document_page`, `document_search` are named
routes under `/api/media/`. Inspection runs no OCR. Toolserver's optional media
catalog exposes `pdf_text`, `document_inspect`, `document_page`, `document_search`.
`pdf_text` uploads caller-local files, returns the persisted server `source`, and
honors `ocr_if_empty`; pass `source` plus `artifact_id` for subsequent reads.

Version 0.2 replaces document/ocr facades. `process_pdf/process_pdfs/pdf_pages` now
return the documented artifact shape. Old `DocumentPipeline`, `SliceManager`,
`generate_pdf`, directory/video OCR exports are removed from these namespaces;
consumers of those legacy APIs must migrate or retain their old dependency.
Other media layers are unchanged. Nothing modifies `/srv/pyit/dev`.

## Validation limits

Tests use generated documents and mocked OCR transport. They verify coverage,
source identity, retries, limits and structure. They do not establish OCR accuracy
on real documents. Complex multi-column layouts, unruled/nested PDF tables, charts,
handwriting and embedded Office images still need evaluation. Native text in an
Office document does not imply embedded image contents were transcribed.
