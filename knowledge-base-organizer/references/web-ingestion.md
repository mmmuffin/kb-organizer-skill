# Web Ingestion

Use web mode when the source is a documentation website or a set of public pages.

## Defaults

- stay within the same host by default
- prefer a sitemap when available
- otherwise crawl from the entry page
- preserve original HTML under `originals/web/`
- normalize page content into Markdown under `normalized/`

## Extraction expectations

- extract page title, headings, and main content
- avoid global navigation, footers, and table-of-contents noise where possible
- preserve the original online URL in document metadata

## Images

- download content images that are part of the page meaning
- keep source URLs for downloaded images
- relate images back to the parent page in `image_manifest.json`

## Out of scope in v1

- authenticated site automation
- JS-heavy browser-only rendering workflows that require logged-in browser control
- complete website mirroring for offline visual browsing
