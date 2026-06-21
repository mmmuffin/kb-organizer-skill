# Local Normalization

Use local-folder mode when the input is a filesystem directory rather than a website.

## Goals

- keep the source directory untouched
- preserve originals under `originals/local/`
- produce retrieval-oriented Markdown under `normalized/`
- preserve standalone images and OCR sidecars

## File handling defaults

- `md`, `txt`: wrap in metadata and keep text intact
- `html`, `htm`: extract main body text and local image references
- `csv`: preserve original and normalize table content
- `xlsx`, `xls`: extract sheet tables into Markdown sections
- `docx`, `rtf`: use a supported text conversion path
- `pdf`: use the best available extraction path; record failure if extraction is unavailable
- image files: preserve to `images/`, then OCR if possible

## Topic grouping

Use the source directory hierarchy as the default domain/topic heuristic. Do not reorganize aggressively in v1 when the semantic grouping is uncertain.

## Failure handling

Never abort the whole run because one file fails. Preserve the original and record the failure in `run_report.json`.
