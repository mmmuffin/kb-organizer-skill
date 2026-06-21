# Image Handling

Images are first-class retrieval artifacts.

## Preserve

- keep each relevant image in `images/`
- keep the source URI/path
- relate images to the nearest parent document when known
- backfill parent-document linkage even when an image is first discovered as a standalone local file

## Metadata

For each image capture:

- title or alt text
- filename-derived label when no better label exists
- nearby paragraph or page excerpt as `context_excerpt`
- OCR sidecar path
- OCR status
- document linkage in both directions:
  - document `related_images`
  - image `parent_document_id`

## Retrieval intent

The goal is not only to preserve image files but to make them discoverable later through:

- OCR text
- context excerpt
- source/title metadata
- parent-document relationship
- rewritten local Markdown/HTML image references that point at preserved `images/` artifacts

## v1 non-goals

- full chart understanding
- independent visual summaries beyond OCR + context
- extracting embedded images from every proprietary document format
