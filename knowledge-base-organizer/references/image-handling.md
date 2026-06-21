# Image Handling

Images are first-class retrieval artifacts.

## Preserve

- keep each relevant image in `images/`
- keep the source URI/path
- relate images to the nearest parent document when known

## Metadata

For each image capture:

- title or alt text
- filename-derived label when no better label exists
- nearby paragraph or page excerpt as `context_excerpt`
- OCR sidecar path
- OCR status

## Retrieval intent

The goal is not only to preserve image files but to make them discoverable later through:

- OCR text
- context excerpt
- source/title metadata

## v1 non-goals

- full chart understanding
- independent visual summaries beyond OCR + context
- extracting embedded images from every proprietary document format
