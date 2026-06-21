# knowledge-base-organizer

Organize a local folder or documentation website into a retrieval-ready local knowledge package.

This repository is intentionally structured as a **single installable skill root**, so the repository root is the skill directory itself.

## What changed in v1.2.1

- default OCR profile is now `mobile`, not a heavy server-grade default
- the organizer can start on a fresh machine and detect missing runtime dependencies
- when dependencies are missing, the organizer can show a bootstrap plan and install the recommended stack after confirmation
- if installation is skipped or fails, the run can still continue in degraded mode and record the loss of recall capability in `run_report.json`
- local Markdown image references are now rewritten to packaged `images/` artifacts
- document-linked images now keep stronger recall metadata:
  - `manifest.json.related_images`
  - `image_manifest.json.parent_document_id`
  - `context_excerpt`
  - rewritten normalized image paths
- `data_structure.md` now surfaces source provenance and image-linked retrieval hints

## Repository structure

```text
.
├── README.md
├── README.zh-CN.md
├── SKILL.md
├── manifest.json
├── agents/
├── references/
└── scripts/
```

## Install

Copy this repository root into your Codex skills directory using the folder name `knowledge-base-organizer`:

```bash
cp -R . "${CODEX_HOME:-$HOME/.codex}/skills/knowledge-base-organizer"
```

If you cloned the repo elsewhere, copy the whole repo directory, not just individual files.

## Fastest way to start

Check the current machine:

```bash
python3 scripts/organize_kb.py --check-deps
```

Organize a local knowledge source with the default lightweight profile:

```bash
python3 scripts/organize_kb.py \
  --input /absolute/path/to/source-folder \
  --output /absolute/path/to/organized-kb \
  --mode local \
  --ocr-profile mobile
```

Organize a documentation website:

```bash
python3 scripts/organize_kb.py \
  --input https://docs.example.com/start-page \
  --output /absolute/path/to/organized-kb \
  --mode web \
  --ocr-profile mobile \
  --crawl-limit 40
```

## Fresh-machine behavior

By default:

- `--ocr-profile mobile`
- `--install-missing prompt`
- interactive terminal: show the bootstrap plan, ask for confirmation, then install
- non-interactive terminal: do not auto-install, continue in degraded mode when possible

Manual bootstrap is also available:

```bash
python3 scripts/bootstrap_env.py --profile mobile
```

Non-interactive bootstrap for CI or automated setup:

```bash
python3 scripts/bootstrap_env.py --profile mobile --yes
```

## Runtime profiles

### `none`

- best for text-first knowledge bases
- no OCR guarantee
- scanned PDFs will not become retrieval-ready text

### `mobile`

- default profile
- recommended for new laptops, desktops, and Ubuntu VPSes
- uses:
  - `PP-OCRv5_mobile_det`
  - `PP-OCRv5_mobile_rec`
- best balance of size, speed, and recall quality

### `server`

- heavier profile
- only use when the user explicitly wants higher OCR accuracy and accepts higher runtime cost

## PDF and image strategy

- native-text PDFs: `pdftotext` first, then `pypdf`
- scanned PDFs: `pdftoppm` to rasterize pages, then OCR the page images
- standalone images: preserve the image and generate OCR sidecar text when possible
- temporary page images for scanned-PDF OCR are stored in a temp directory and removed after processing

## What “retrieval-ready” now means

For mixed document libraries, the organizer now tries to preserve the full recall chain instead of
only preserving files:

- a normalized document keeps `related_images`
- a preserved image keeps `parent_document_id` when the organizer can infer its parent document
- local Markdown and HTML image references are rewritten to packaged `images/` files
- `context_excerpt`, `title_or_alt`, and `source_uri` stay available for downstream retrieval

This matters because downstream agents usually need to answer questions like “show me the diagram
from that guide” or “which screenshot explains this flow,” not just “list all image files.”

## What “degraded mode” means

If the recommended stack is unavailable and bootstrap is skipped or fails:

- the organizer still preserves originals
- text-like files can still be normalized when their own dependencies exist
- images still enter `image_manifest.json`
- scanned PDFs still remain traceable through originals and failure records
- `run_report.json` records:
  - dependency status
  - selected OCR profile
  - capability matrix
  - whether the run was degraded

## How downstream retrieval should recall images

Retrieval should not rely on OCR text alone. Use:

- `image_manifest.json`
- `manifest.json.related_images`
- parent document relationship
- `title_or_alt`
- `context_excerpt`
- `source_uri`
- OCR sidecar text when available

This lets downstream agents recall the right image even when OCR is partial or unavailable.

## Recommended downstream workflow

```text
raw knowledge source
-> knowledge-base-organizer
-> organized knowledge package
-> retriever skill and/or MCP
-> answering agent
```

## Documentation

- Chinese documentation: [`README.zh-CN.md`](./README.zh-CN.md)
- Skill instructions for Codex: [`SKILL.md`](./SKILL.md)
- Capability notes: [`references/capability-matrix.md`](./references/capability-matrix.md)
