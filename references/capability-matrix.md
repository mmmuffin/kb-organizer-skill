# Capability Matrix

Use this file to decide which runtime profile is appropriate for a given knowledge source.

## Profiles

### `none`

- target use case: text-first knowledge bases
- installs:
  - core Python dependencies
  - `pypdf` fallback
- does not guarantee:
  - image OCR
  - scanned-PDF OCR
  - strong native-PDF extraction

### `mobile`

- default profile
- target use case: mixed knowledge bases on new devices or VPSes
- installs:
  - core Python dependencies
  - `paddlepaddle` CPU runtime
  - `paddleocr`
  - `pypdf`
  - Poppler (`pdftotext`, `pdftoppm`)
- guarantees best balance of:
  - install size
  - OCR availability
  - scanned-PDF handling
  - first-run usability

### `server`

- target use case: higher OCR accuracy on better machines
- installs the same runtime stack as `mobile`
- changes the PaddleOCR model selection to server-grade detection/recognition models
- not the default for new devices

## Source-Type Expectations

### Pure text / Markdown / HTML

- required: core Python dependencies
- OCR not required

### Native-text PDF

- best path: `pdftotext`
- fallback: `pypdf`
- recommendation: `mobile`

### Scanned PDF

- required:
  - `pdftoppm`
  - OCR profile `mobile` or `server`
- recommendation: `mobile`

### Image-heavy knowledge base

- required:
  - preserved original images
  - OCR sidecars when available
  - image metadata
- recommendation: `mobile`

## Retrieval Notes

AI should not rely on OCR text alone. Downstream retrieval should use:

- `image_manifest.json`
- parent document relationship
- `title_or_alt`
- `context_excerpt`
- `source_uri`
- OCR sidecar text when present

If OCR is unavailable, the image should still remain recallable through metadata and document context, but text-level recall quality will be lower.
