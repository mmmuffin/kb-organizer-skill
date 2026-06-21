# knowledge-base-organizer

Organize a local folder or documentation website into a retrieval-ready local knowledge package.

This repository is intentionally structured as a **single installable skill root**, so the repository root is the skill directory itself.

## What it does

- sync a public documentation site into a local knowledge package
- normalize mixed local documents into Markdown
- preserve original files and original page HTML
- preserve images as first-class artifacts
- generate OCR sidecar text for images when possible
- emit retrieval-oriented outputs such as:
  - `data_structure.md`
  - `manifest.json`
  - `image_manifest.json`
  - `source_map.json`
  - `run_report.json`

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

## Runtime dependencies

Core Python packages:

```bash
pip install pandas requests beautifulsoup4 pillow
```

Recommended extras:

```bash
pip install pypdf openpyxl lxml
```

Optional OCR:

```bash
pip install pytesseract
```

System OCR example on macOS:

```bash
brew install tesseract
```

## Quick start

Local folder:

```bash
python3 scripts/organize_kb.py \
  --input /absolute/path/to/source-folder \
  --output /absolute/path/to/organized-kb \
  --mode local
```

Documentation website:

```bash
python3 scripts/organize_kb.py \
  --input https://docs.example.com/start-page \
  --output /absolute/path/to/organized-kb \
  --mode web \
  --crawl-limit 40
```

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
