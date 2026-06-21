---
name: knowledge-base-organizer
description: "Organize a local folder or documentation website into a retrieval-ready local knowledge package with normalized Markdown, preserved originals, directory indices, manifests, and image OCR metadata. Use when Codex needs to: (1) sync an online documentation site into a local knowledge base, (2) clean up a mixed local document folder for later retrieval, (3) generate `data_structure.md`, `manifest.json`, or `image_manifest.json`, (4) preserve source traceability while normalizing content, or (5) prepare a knowledge base for downstream MCP tools or retrieval skills instead of vector RAG."
---

# Knowledge Base Organizer

Use this skill to perform the first-stage knowledge-base pipeline: inspect a source, normalize it into a new output directory, preserve the source artifacts, extract image OCR when possible, and emit retrieval-oriented metadata for later skills or MCP servers.

## Quick Start

Choose the source type, then run the organizer script:

```bash
python3 scripts/organize_kb.py \
  --input /absolute/path/to/source-folder \
  --output /absolute/path/to/organized-kb \
  --mode local
```

```bash
python3 scripts/organize_kb.py \
  --input https://docs.example.com/start-page \
  --output /absolute/path/to/organized-kb \
  --mode web \
  --crawl-limit 40
```

Default rule: always write to a new output directory. Do not mutate the source knowledge base unless the user explicitly asks for a different workflow.

## Workflow

### 1. Inspect the source

- Determine whether the input is a local folder, a documentation URL, or ambiguous.
- Prefer `--mode auto` only when the source type is obvious from the input.
- Estimate whether the source is primarily text, document files, or image-heavy.

### 2. Normalize into a new package

The organizer emits a package like:

```text
<organized-kb>/
  data_structure.md
  manifest.json
  image_manifest.json
  source_map.json
  run_report.json
  normalized/
  originals/
  images/
  ocr/
```

- `normalized/` contains retrieval-oriented Markdown.
- `originals/` preserves the original source artifacts.
- `images/` contains downloaded or copied image files.
- `ocr/` contains OCR sidecar text when OCR succeeds.

### 3. Handle local folders

- Recursively scan files.
- Preserve originals under `originals/local/`.
- Normalize text-like files into Markdown under `normalized/`.
- Preserve standalone images and attach OCR/metadata when possible.
- Use parent directories as the default domain/topic grouping heuristic.

For local normalization details, read:
- `references/local-normalization.md`
- `references/output-schema.md`

### 4. Handle documentation websites

- Prefer a sitemap when present. Otherwise crawl from the entry page within the same host and path family.
- Preserve original HTML under `originals/web/`.
- Extract the main content into Markdown under `normalized/`.
- Download content images that should remain recallable later.
- Keep original online URLs in document metadata for future user-facing citations.

For website-specific rules, read:
- `references/web-ingestion.md`
- `references/image-handling.md`

### 5. Handle images and OCR

- Treat images as first-class artifacts, not as disposable attachments.
- Preserve each relevant image in `images/`.
- Create an `image_manifest.json` entry with:
  - image path
  - source URI
  - parent document relation when known
  - alt/title/context excerpt
  - OCR text path
  - OCR status
- OCR is best-effort and backend-pluggable. If OCR is unavailable or fails, preserve the image and mark the failure in metadata instead of dropping the image.

OCR contract and fallback behavior are in:
- `references/ocr-backends.md`
- `references/image-handling.md`

### 6. Generate retrieval-oriented metadata

- Generate `manifest.json` for document-level metadata.
- Generate `image_manifest.json` for image-level metadata.
- Generate `source_map.json` to preserve source-to-output traceability.
- Generate `data_structure.md` at the root and major subdirectories so directory-driven retrieval skills can navigate the package.

### 7. Validate the package

The run is only complete when:
- the source input is untouched
- the output package is self-contained
- each normalized document maps back to its source
- images are preserved even if OCR fails
- `run_report.json` captures failures, skips, and counts

## Resource Routing

- Run `scripts/organize_kb.py` for actual organization work.
- Read `references/output-schema.md` to understand required output fields and directory layout.
- Read `references/local-normalization.md` when the source is a local folder.
- Read `references/web-ingestion.md` when the source is a documentation site.
- Read `references/image-handling.md` and `references/ocr-backends.md` when images or OCR behavior matter.

## Defaults

- Default mode: write into a new output directory
- Default downstream target: compatible with both retrieval skills and MCP wrappers
- Default citation expectation for online sources: keep original online URLs in metadata
- Default OCR expectation: OCR + surrounding context metadata, not full visual-semantic interpretation
