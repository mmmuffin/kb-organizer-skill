# OCR Backends

OCR is pluggable and best-effort.

## Contract

The organizer should expose one OCR interface that returns:

- extracted text
- backend name
- status
- optional error message

## Preferred backend order

1. explicit profile selected by the caller
2. `mobile` profile via PaddleOCR
3. `server` profile via PaddleOCR when explicitly requested
4. `tesseract` CLI if PaddleOCR is unavailable
5. unavailable status if no OCR engine exists

## Current v2 strategy

- use `PaddleOCR mobile` as the default OCR engine for:
  - standalone images
  - downloaded web images
  - rasterized PDF pages during scanned-PDF fallback
- keep `PaddleOCR server` as an opt-in heavier profile
- keep `tesseract` CLI as a lightweight fallback
- do not require OCR for the whole run to succeed

## Failure behavior

- do not drop images when OCR fails
- still emit `image_manifest.json` records
- write an OCR sidecar only when text extraction succeeds
- record failure details in `run_report.json`
