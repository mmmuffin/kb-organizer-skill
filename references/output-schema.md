# Output Schema

The organizer emits a retrieval-ready package with these required artifacts:

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

## `manifest.json`

Each document entry must include:

- `id`
- `title`
- `source_type`
- `source_uri`
- `normalized_path`
- `original_path`
- `content_type`
- `domain`
- `summary`
- `headings`
- `keywords`
- `related_images`
- `last_synced_at`
- `source_last_modified`

## `image_manifest.json`

Each image entry must include:

- `id`
- `image_path`
- `source_uri`
- `parent_document_id`
- `title_or_alt`
- `context_excerpt`
- `ocr_text_path`
- `keywords`
- `width`
- `height`
- `ocr_status`

## `source_map.json`

Track both directions:

- source URI/path -> normalized document
- source URI/path -> preserved original
- source URI/path -> images derived from that source

## `run_report.json`

Include:

- input source
- mode
- counts by artifact type
- OCR success/failure counts
- skipped items
- failures with reasons
- validation checks
