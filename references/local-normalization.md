# Local Normalization

Use local-folder mode when the input is a filesystem directory rather than a website.

## Goals

- keep the source directory untouched
- preserve originals under `originals/local/`
- produce retrieval-oriented Markdown under `normalized/`
- preserve standalone images and OCR sidecars

## File handling defaults

- `md`, `txt`: wrap in metadata and keep text intact; when Markdown contains local image references, preserve the image, rewrite the normalized path to the packaged `images/` artifact, and link the image back to the document
- `html`, `htm`: extract main body text and local image references
- `csv`: preserve original and normalize table content
- `xlsx`, `xls`: extract sheet tables into Markdown sections
- `docx`, `rtf`: use a supported text conversion path
- `pdf`: prefer `pdftotext` from Poppler for text PDFs; if extracted text is missing or insufficient, try `pypdf`, then rasterize pages with `pdftoppm` and OCR them
- image files: preserve to `images/`, then OCR if possible

## PDF strategy

Process PDFs in layers:

1. keep the original PDF under `originals/local/`
2. try `pdftotext` first for native-text PDFs
3. optionally use a Python text fallback when available
4. if the PDF still has no meaningful text, use `pdftoppm` to rasterize pages
5. OCR rasterized pages with the configured OCR profile, defaulting to `mobile`
6. write the final merged text into `normalized/`

## Topic grouping

Use the source directory hierarchy as the default domain/topic heuristic. Do not reorganize aggressively in v1 when the semantic grouping is uncertain.

## Failure handling

Never abort the whole run because one file fails. Preserve the original and record the failure in `run_report.json`.
