#!/usr/bin/env python3
"""Organize a local folder or documentation website into a retrieval-ready knowledge package."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image

USER_AGENT = "KnowledgeBaseOrganizer/1.0"
TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
HTML_EXTENSIONS = {".html", ".htm"}
SPREADSHEET_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls"}
DOC_EXTENSIONS = {".docx", ".rtf", ".doc"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg"}
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "your", "have",
    "will", "when", "what", "how", "why", "are", "use", "using", "can", "not",
    "文档", "知识库", "以及", "这个", "那个", "一个", "我们", "你们", "页面", "目录", "内容",
}


@dataclass
class OCRResult:
    text: str
    backend: str
    status: str
    error: str | None = None


@dataclass
class ImageRecord:
    id: str
    image_path: str
    source_uri: str
    parent_document_id: str | None
    title_or_alt: str
    context_excerpt: str
    ocr_text_path: str | None
    keywords: list[str]
    width: int | None
    height: int | None
    ocr_status: str
    ocr_backend: str | None = None
    ocr_error: str | None = None


@dataclass
class DocumentRecord:
    id: str
    title: str
    source_type: str
    source_uri: str
    normalized_path: str
    original_path: str
    content_type: str
    domain: str
    summary: str
    headings: list[str]
    keywords: list[str]
    related_images: list[str]
    last_synced_at: str
    source_last_modified: str | None


@dataclass
class RunReport:
    input_source: str
    mode: str
    started_at: str
    finished_at: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    failures: list[dict[str, str]] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    validations: list[dict[str, Any]] = field(default_factory=list)


class OCRBackend:
    def __init__(self, preferred: str = "auto") -> None:
        self.preferred = preferred
        self._paddle_instance: Any | None = None

    def extract(self, image_path: Path) -> OCRResult:
        for backend in self._candidate_backends():
            if backend == "paddleocr":
                result = self._extract_paddleocr(image_path)
            elif backend == "tesseract-cli":
                result = self._extract_tesseract_cli(image_path)
            elif backend == "none":
                result = OCRResult(text="", backend="none", status="unavailable", error="No OCR backend available")
            else:
                continue
            if result.status in {"ok", "empty", "unavailable"} or result.error:
                return result
        return OCRResult(text="", backend="none", status="unavailable", error="No OCR backend available")

    def _candidate_backends(self) -> list[str]:
        if self.preferred != "auto":
            return [self.preferred]
        candidates: list[str] = []
        try:
            from paddleocr import PaddleOCR  # type: ignore  # noqa: F401
            candidates.append("paddleocr")
        except Exception:
            pass
        if shutil.which("tesseract"):
            candidates.append("tesseract-cli")
        candidates.append("none")
        return candidates

    def _extract_paddleocr(self, image_path: Path) -> OCRResult:
        try:
            from paddleocr import PaddleOCR  # type: ignore

            if self._paddle_instance is None:
                # Default to the general Chinese+English model family, which works
                # reasonably well for mixed Chinese/English documentation screenshots.
                self._paddle_instance = PaddleOCR(lang="ch")
            result = self._paddle_instance.ocr(str(image_path), cls=True)
            text = extract_text_from_paddle_result(result)
            return OCRResult(text=text, backend="paddleocr", status="ok" if text else "empty")
        except Exception as exc:
            return OCRResult(text="", backend="paddleocr", status="failed", error=str(exc))

    def _extract_tesseract_cli(self, image_path: Path) -> OCRResult:
        try:
            completed = subprocess.run(
                ["tesseract", str(image_path), "stdout"],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                return OCRResult(text="", backend="tesseract-cli", status="failed", error=completed.stderr.strip() or "tesseract failed")
            text = completed.stdout.strip()
            return OCRResult(text=text, backend="tesseract-cli", status="ok" if text else "empty")
        except Exception as exc:
            return OCRResult(text="", backend="tesseract-cli", status="failed", error=str(exc))


class Organizer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.input_source = args.input
        self.output_dir = Path(args.output).resolve()
        self.mode = self._detect_mode(args.input, args.mode)
        self.synced_at = iso_now()
        self.report = RunReport(input_source=args.input, mode=self.mode, started_at=self.synced_at)
        self.ocr_backend = OCRBackend(args.ocr_backend)
        self.documents: list[DocumentRecord] = []
        self.images: list[ImageRecord] = []
        self.source_map: dict[str, dict[str, Any]] = {"documents": {}, "images": {}}
        self.image_id_by_source: dict[str, str] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def run(self) -> None:
        if self.output_dir.exists() and any(self.output_dir.iterdir()):
            raise SystemExit(f"Output directory must be new or empty: {self.output_dir}")
        self._ensure_output_dirs()

        if self.mode == "local":
            self.organize_local(Path(self.input_source).resolve())
        elif self.mode == "web":
            self.organize_web(self.input_source)
        else:
            raise SystemExit(f"Unsupported mode: {self.mode}")

        self.write_indices()
        self.validate_output()
        self.report.finished_at = iso_now()
        self.report.counts = {
            "documents": len(self.documents),
            "images": len(self.images),
            "ocr_success": sum(1 for image in self.images if image.ocr_status == "ok"),
            "ocr_empty": sum(1 for image in self.images if image.ocr_status == "empty"),
            "ocr_failed": sum(1 for image in self.images if image.ocr_status in {"failed", "unavailable"}),
        }
        write_json(self.output_dir / "manifest.json", [asdict(doc) for doc in self.documents])
        write_json(self.output_dir / "image_manifest.json", [asdict(image) for image in self.images])
        write_json(self.output_dir / "source_map.json", self.source_map)
        write_json(self.output_dir / "run_report.json", asdict(self.report))

    def organize_local(self, source_dir: Path) -> None:
        if not source_dir.is_dir():
            raise SystemExit(f"Local input must be a directory: {source_dir}")

        for path in sorted(source_dir.rglob("*")):
            if path.is_dir() or self._is_hidden(path, source_dir):
                continue
            rel = path.relative_to(source_dir)
            source_uri = str(path.resolve())
            original_path = self.copy_original(path, Path("local") / rel)
            kind = classify_file(path)

            if kind == "image":
                self.process_image_file(path, source_uri, None, path.stem)
                continue
            if kind == "unsupported":
                self.report.skipped.append({"source": source_uri, "reason": "Unsupported file type"})
                continue

            try:
                normalized, title, headings, summary, related_images, keywords = self.normalize_local_document(path, rel, kind)
                normalized_path = self.write_normalized(rel.with_suffix(".md"), normalized)
                domain = rel.parent.as_posix() if rel.parent.as_posix() != "." else "root"
                record = DocumentRecord(
                    id=stable_id(f"doc::{source_uri}"),
                    title=title,
                    source_type="local",
                    source_uri=source_uri,
                    normalized_path=normalized_path,
                    original_path=original_path,
                    content_type=kind,
                    domain=domain,
                    summary=summary,
                    headings=headings,
                    keywords=keywords,
                    related_images=related_images,
                    last_synced_at=self.synced_at,
                    source_last_modified=dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat(),
                )
                self.documents.append(record)
                self.source_map["documents"][source_uri] = {
                    "normalized_path": normalized_path,
                    "original_path": original_path,
                }
            except Exception as exc:
                self.report.failures.append({"source": source_uri, "reason": str(exc)})

    def organize_web(self, start_url: str) -> None:
        for url in self.collect_web_urls(start_url):
            try:
                response = self.session.get(url, timeout=self.args.timeout)
                response.raise_for_status()
                html_text = response.text
                original_path = self.write_original_html(web_original_rel(url), html_text)
                normalized, title, headings, summary, related_images = self.normalize_web_document(url, html_text)
                normalized_path = self.write_normalized(web_normalized_rel(url), normalized)
                keywords = extract_keywords("\n".join([title, summary, "\n".join(headings)]))
                record = DocumentRecord(
                    id=stable_id(f"doc::{url}"),
                    title=title,
                    source_type="web",
                    source_uri=url,
                    normalized_path=normalized_path,
                    original_path=original_path,
                    content_type="html",
                    domain=web_domain_name(url),
                    summary=summary,
                    headings=headings,
                    keywords=keywords,
                    related_images=related_images,
                    last_synced_at=self.synced_at,
                    source_last_modified=response.headers.get("Last-Modified"),
                )
                self.documents.append(record)
                self.source_map["documents"][url] = {
                    "normalized_path": normalized_path,
                    "original_path": original_path,
                }
            except Exception as exc:
                self.report.failures.append({"source": url, "reason": str(exc)})

    def collect_web_urls(self, start_url: str) -> list[str]:
        sitemap_url = self.args.sitemap_url or urllib.parse.urljoin(start_url, "/sitemap.xml")
        urls: list[str] = []
        try:
            response = self.session.get(sitemap_url, timeout=self.args.timeout)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = [
                loc.text.strip()
                for loc in root.findall(".//sm:loc", ns)
                if loc.text and self._allowed_web_url(loc.text.strip(), start_url)
            ]
        except Exception:
            urls = []
        if urls:
            return sorted(dedupe(urls))[: self.args.crawl_limit]
        return self.crawl_web_urls(start_url)

    def crawl_web_urls(self, start_url: str) -> list[str]:
        queue = [start_url]
        seen: set[str] = set()
        collected: list[str] = []
        while queue and len(collected) < self.args.crawl_limit:
            url = queue.pop(0)
            if url in seen or not self._allowed_web_url(url, start_url):
                continue
            seen.add(url)
            try:
                response = self.session.get(url, timeout=self.args.timeout)
                response.raise_for_status()
                collected.append(url)
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.find_all("a", href=True):
                    next_url = strip_fragment(urllib.parse.urljoin(url, link["href"]))
                    if next_url not in seen and self._allowed_web_url(next_url, start_url):
                        queue.append(next_url)
            except Exception as exc:
                self.report.failures.append({"source": url, "reason": f"crawl failed: {exc}"})
        return collected

    def normalize_local_document(self, path: Path, rel: Path, kind: str) -> tuple[str, str, list[str], str, list[str], list[str]]:
        if kind in {"markdown", "text"}:
            body = path.read_text(encoding="utf-8", errors="replace")
            headings = extract_markdown_headings(body)
            related_images: list[str] = []
        elif kind == "html":
            body, headings, related_images = self.normalize_html_common(
                f"file://{path.resolve()}",
                path.read_text(encoding="utf-8", errors="replace"),
                path.parent,
                rel.with_suffix(".md"),
            )
        elif kind == "spreadsheet":
            body = extract_spreadsheet_markdown(path)
            headings = [path.stem]
            related_images = []
        elif kind == "doc":
            body = extract_text_via_textutil(path)
            headings = [path.stem]
            related_images = []
        elif kind == "pdf":
            body = self.extract_pdf_document(path)
            headings = [path.stem]
            related_images = []
        else:
            raise ValueError(f"Unsupported normalization kind: {kind}")

        title = headings[0] if headings else extract_title_from_text(path.stem, body)
        summary = first_summary_line(body)
        keywords = extract_keywords("\n".join([title, summary, "\n".join(headings)]))
        markdown = build_markdown_document(title, f"file://{path.resolve()}", "local", self.synced_at, body, str(rel), None, related_images)
        return markdown, title, headings, summary, related_images, keywords

    def normalize_web_document(self, url: str, html_text: str) -> tuple[str, str, list[str], str, list[str]]:
        body, headings, related_images = self.normalize_html_common(url, html_text, None, Path(web_normalized_rel(url)))
        title = headings[0] if headings else extract_title_from_text(Path(web_normalized_rel(url)).stem, body)
        summary = first_summary_line(body)
        markdown = build_markdown_document(title, url, "web", self.synced_at, body, web_normalized_rel(url), None, related_images)
        return markdown, title, headings, summary, related_images

    def normalize_html_common(
        self,
        source_uri: str,
        html_text: str,
        local_base: Path | None,
        doc_rel: Path,
    ) -> tuple[str, list[str], list[str]]:
        soup = BeautifulSoup(html_text, "html.parser")
        root = find_content_root(soup)
        headings: list[str] = []
        related_images: list[str] = []
        blocks: list[str] = []

        for child in root.children:
            rendered, child_headings, child_images = self.render_html_node(child, source_uri, local_base, doc_rel)
            if rendered:
                blocks.append(rendered)
            headings.extend(child_headings)
            related_images.extend(child_images)
        body = "\n\n".join(block for block in blocks if block).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        return body, dedupe(headings), dedupe(related_images)

    def render_html_node(
        self,
        node: Any,
        source_uri: str,
        local_base: Path | None,
        doc_rel: Path,
    ) -> tuple[str, list[str], list[str]]:
        if isinstance(node, NavigableString):
            text = clean_text(str(node))
            return text, [], []
        if not isinstance(node, Tag):
            return "", [], []
        if node.name in {"script", "style", "nav", "footer"}:
            return "", [], []

        headings: list[str] = []
        related_images: list[str] = []
        if node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            text = clean_text(node.get_text(" ", strip=True))
            if text:
                headings.append(text)
                return f"{'#' * int(node.name[1])} {text}", headings, related_images
            return "", headings, related_images
        if node.name in {"p", "span"}:
            return clean_text(node.get_text(" ", strip=True)), headings, related_images
        if node.name in {"ul", "ol"}:
            return html_list_to_markdown(node), headings, related_images
        if node.name == "pre":
            return f"```\n{node.get_text(chr(10), strip=False).strip()}\n```", headings, related_images
        if node.name == "table":
            return html_table_to_markdown(node), headings, related_images
        if node.name == "img":
            image_id, rel_path = self.process_image_from_html(node, source_uri, local_base, doc_rel)
            if image_id and rel_path:
                related_images.append(image_id)
                alt = clean_text(node.get("alt", "") or node.get("title", "") or image_id)
                return f"![{alt}]({rel_path})", headings, related_images
            return "", headings, related_images

        blocks: list[str] = []
        for child in node.children:
            rendered, child_headings, child_images = self.render_html_node(child, source_uri, local_base, doc_rel)
            if rendered:
                blocks.append(rendered)
            headings.extend(child_headings)
            related_images.extend(child_images)
        return "\n\n".join(blocks).strip(), headings, related_images

    def process_image_from_html(
        self,
        tag: Tag,
        source_uri: str,
        local_base: Path | None,
        doc_rel: Path,
    ) -> tuple[str | None, str | None]:
        src = tag.get("src")
        if not src:
            return None, None
        image_source = resolve_resource_uri(source_uri, src, local_base)
        if image_source in self.image_id_by_source:
            image_id = self.image_id_by_source[image_source]
            image_path = next((image.image_path for image in self.images if image.id == image_id), None)
            return image_id, relative_ref_to_image(image_path, doc_rel) if image_path else None

        image_file = self.fetch_or_copy_image(image_source)
        if image_file is None:
            return None, None

        image_id = stable_id(f"img::{image_source}")
        ocr_text_path, ocr_status, backend, error = self.ocr_image(image_file, image_id)
        width, height = image_dimensions(image_file)
        alt = clean_text(tag.get("alt", "") or tag.get("title", "") or Path(urllib.parse.urlparse(image_source).path).stem)
        record = ImageRecord(
            id=image_id,
            image_path=image_file.relative_to(self.output_dir).as_posix(),
            source_uri=image_source,
            parent_document_id=stable_id(f"doc::{source_uri}"),
            title_or_alt=alt,
            context_excerpt=alt[:240],
            ocr_text_path=ocr_text_path,
            keywords=extract_keywords(alt),
            width=width,
            height=height,
            ocr_status=ocr_status,
            ocr_backend=backend,
            ocr_error=error,
        )
        self.images.append(record)
        self.image_id_by_source[image_source] = image_id
        self.source_map["images"][image_source] = {
            "image_path": record.image_path,
            "ocr_text_path": ocr_text_path,
        }
        return image_id, relative_ref_to_image(record.image_path, doc_rel)

    def process_image_file(self, path: Path, source_uri: str, parent_document_id: str | None, context: str) -> None:
        if source_uri in self.image_id_by_source:
            return
        dest = self.output_dir / "images" / f"{stable_id(source_uri)}{path.suffix.lower()}"
        ensure_parent(dest)
        shutil.copy2(path, dest)
        image_id = stable_id(f"img::{source_uri}")
        ocr_text_path, ocr_status, backend, error = self.ocr_image(dest, stable_id(source_uri))
        width, height = image_dimensions(dest)
        record = ImageRecord(
            id=image_id,
            image_path=dest.relative_to(self.output_dir).as_posix(),
            source_uri=source_uri,
            parent_document_id=parent_document_id,
            title_or_alt=path.stem,
            context_excerpt=context[:240],
            ocr_text_path=ocr_text_path,
            keywords=extract_keywords("\n".join([path.stem, context])),
            width=width,
            height=height,
            ocr_status=ocr_status,
            ocr_backend=backend,
            ocr_error=error,
        )
        self.images.append(record)
        self.image_id_by_source[source_uri] = image_id
        self.source_map["images"][source_uri] = {
            "image_path": record.image_path,
            "ocr_text_path": ocr_text_path,
        }

    def fetch_or_copy_image(self, image_source: str) -> Path | None:
        parsed = urllib.parse.urlparse(image_source)
        suffix = Path(parsed.path).suffix.lower() or ".img"
        dest = self.output_dir / "images" / f"{stable_id(image_source)}{suffix}"
        ensure_parent(dest)
        try:
            if parsed.scheme in {"http", "https"}:
                response = self.session.get(image_source, timeout=self.args.timeout)
                response.raise_for_status()
                dest.write_bytes(response.content)
            elif parsed.scheme == "file":
                source_path = Path(urllib.parse.unquote(parsed.path))
                shutil.copy2(source_path, dest)
            elif Path(image_source).exists():
                shutil.copy2(Path(image_source), dest)
            else:
                return None
            return dest
        except Exception as exc:
            self.report.failures.append({"source": image_source, "reason": f"image fetch/copy failed: {exc}"})
            return None

    def copy_original(self, path: Path, rel: Path) -> str:
        dest = self.output_dir / "originals" / rel
        ensure_parent(dest)
        shutil.copy2(path, dest)
        return dest.relative_to(self.output_dir).as_posix()

    def write_original_html(self, rel: str, html_text: str) -> str:
        dest = self.output_dir / "originals" / "web" / rel
        ensure_parent(dest)
        dest.write_text(html_text, encoding="utf-8")
        return dest.relative_to(self.output_dir).as_posix()

    def write_normalized(self, rel: str | Path, markdown: str) -> str:
        dest = self.output_dir / "normalized" / rel
        ensure_parent(dest)
        dest.write_text(markdown, encoding="utf-8")
        return dest.relative_to(self.output_dir).as_posix()

    def ocr_image(self, image_path: Path, image_id: str) -> tuple[str | None, str, str | None, str | None]:
        result = self.ocr_backend.extract(image_path)
        if result.status == "ok" and result.text:
            rel = Path("ocr") / f"{image_id}.ocr.txt"
            dest = self.output_dir / rel
            ensure_parent(dest)
            dest.write_text(result.text.strip() + "\n", encoding="utf-8")
            return rel.as_posix(), result.status, result.backend, result.error
        return None, result.status, result.backend, result.error

    def extract_pdf_document(self, path: Path) -> str:
        errors: list[str] = []

        text = extract_pdf_text_via_pdftotext(path)
        if pdf_has_meaningful_text(text):
            return text
        if shutil.which("pdftotext"):
            errors.append("pdftotext produced no meaningful text")
        else:
            errors.append("pdftotext not available")

        text = extract_pdf_text_via_pypdf(path)
        if pdf_has_meaningful_text(text):
            return text

        text, ocr_errors = extract_pdf_text_via_ocr(path, self.ocr_backend)
        if pdf_has_meaningful_text(text):
            return text
        errors.extend(ocr_errors)

        if not errors:
            if not shutil.which("pdftotext"):
                errors.append("pdftotext not available")
            if not shutil.which("pdftoppm"):
                errors.append("pdftoppm not available")
            errors.append("No PDF extraction backend produced usable text")
        raise RuntimeError("; ".join(dedupe(errors)))

    def write_indices(self) -> None:
        docs_by_dir: defaultdict[str, list[DocumentRecord]] = defaultdict(list)
        child_dirs: defaultdict[str, set[str]] = defaultdict(set)
        for doc in self.documents:
            rel = Path(doc.normalized_path).relative_to("normalized")
            directory = rel.parent.as_posix() if rel.parent.as_posix() != "." else ""
            docs_by_dir[directory].append(doc)
            parts = list(rel.parent.parts)
            for idx in range(len(parts)):
                parent = Path(*parts[:idx]).as_posix()
                child_dirs[parent].add(parts[idx])

        all_dirs = set(docs_by_dir) | set(child_dirs) | {""}
        for directory in sorted(all_dirs):
            target_dir = self.output_dir / "normalized" / directory if directory else self.output_dir / "normalized"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "data_structure.md").write_text(
                generate_data_structure(directory, docs_by_dir.get(directory, []), sorted(child_dirs.get(directory, set()))),
                encoding="utf-8",
            )
        (self.output_dir / "data_structure.md").write_text(generate_root_data_structure(self.documents, self.images), encoding="utf-8")

    def validate_output(self) -> None:
        required = ["normalized", "originals", "images", "ocr", "data_structure.md"]
        for name in required:
            path = self.output_dir / name
            self.report.validations.append({"path": str(path), "exists": path.exists()})

    def _ensure_output_dirs(self) -> None:
        for name in ["normalized", "originals", "images", "ocr"]:
            (self.output_dir / name).mkdir(parents=True, exist_ok=True)

    def _detect_mode(self, input_value: str, requested: str) -> str:
        if requested != "auto":
            return requested
        if re.match(r"^https?://", input_value):
            return "web"
        if Path(input_value).exists():
            return "local"
        raise SystemExit(f"Could not infer source mode for input: {input_value}")

    def _allowed_web_url(self, candidate: str, start_url: str) -> bool:
        parsed = urllib.parse.urlparse(candidate)
        start = urllib.parse.urlparse(start_url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if self.args.same_host_only and parsed.netloc != start.netloc:
            return False
        if self.args.path_prefix_only and not parsed.path.startswith(start.path.rstrip("/") or "/"):
            return False
        return True

    def _is_hidden(self, path: Path, root: Path) -> bool:
        rel = path.relative_to(root)
        return any(part.startswith(".") for part in rel.parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Source folder path or documentation URL")
    parser.add_argument("--output", required=True, help="New output directory for the organized knowledge package")
    parser.add_argument("--mode", choices=["auto", "local", "web"], default="auto")
    parser.add_argument("--ocr-backend", default="auto", help="OCR backend: auto, paddleocr, tesseract-cli, none")
    parser.add_argument("--sitemap-url", help="Optional sitemap URL for web mode")
    parser.add_argument("--crawl-limit", type=int, default=40, help="Maximum number of pages to collect in web mode")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--same-host-only", action=argparse.BooleanOptionalAction, default=True, help="Restrict crawling to the same host")
    parser.add_argument("--path-prefix-only", action=argparse.BooleanOptionalAction, default=False, help="Restrict crawling to the same path prefix")
    return parser.parse_args()


def classify_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return "markdown" if suffix in {".md", ".markdown"} else "text"
    if suffix in HTML_EXTENSIONS:
        return "html"
    if suffix in SPREADSHEET_EXTENSIONS:
        return "spreadsheet"
    if suffix in DOC_EXTENSIONS:
        return "doc"
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return "unsupported"


def build_markdown_document(
    title: str,
    source_uri: str,
    source_type: str,
    synced_at: str,
    body: str,
    logical_path: str,
    source_last_modified: str | None,
    related_images: list[str],
) -> str:
    frontmatter = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"source_uri: {json.dumps(source_uri, ensure_ascii=False)}",
        f"source_type: {json.dumps(source_type)}",
        f"logical_path: {json.dumps(logical_path, ensure_ascii=False)}",
        f"last_synced_at: {json.dumps(synced_at)}",
        f"related_images: {json.dumps(related_images, ensure_ascii=False)}",
    ]
    if source_last_modified:
        frontmatter.append(f"source_last_modified: {json.dumps(source_last_modified)}")
    frontmatter.append("---")
    cleaned_body = body.strip()
    title_heading = f"# {title}".strip()
    if cleaned_body.startswith(title_heading):
        return "\n".join(frontmatter) + "\n\n" + cleaned_body + "\n"
    return "\n".join(frontmatter) + "\n\n# " + title + "\n\n" + cleaned_body + "\n"


def extract_markdown_headings(body: str) -> list[str]:
    headings = []
    for line in body.splitlines():
        if line.startswith("#"):
            heading = clean_text(line.lstrip("#").strip())
            if heading:
                headings.append(heading)
    return headings


def extract_title_from_text(default: str, body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped:
            return stripped[:120]
    return default


def first_summary_line(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "|", "-", "```", "![", ">")):
            continue
        return stripped[:240]
    return ""


def extract_spreadsheet_markdown(path: Path) -> str:
    suffix = path.suffix.lower()
    sections: list[str] = []
    if suffix in {".csv", ".tsv"}:
        df = pd.read_csv(path, delimiter="\t" if suffix == ".tsv" else ",")
        return f"## {path.stem}\n\n" + dataframe_to_markdown(df)
    workbook = pd.ExcelFile(path)
    for sheet_name in workbook.sheet_names:
        df = workbook.parse(sheet_name)
        sections.append(f"## Sheet: {sheet_name}\n\n" + dataframe_to_markdown(df))
    return "\n\n".join(sections)


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    safe_df = df.fillna("").astype(str)
    headers = [str(col) for col in safe_df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in safe_df.values.tolist()[:200]:
        lines.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def extract_text_via_textutil(path: Path) -> str:
    completed = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "textutil conversion failed")
    return completed.stdout.strip()


def extract_pdf_text_via_pdftotext(path: Path) -> str:
    if not shutil.which("pdftotext"):
        return ""
    try:
        completed = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return ""
        return normalize_pdf_text(completed.stdout)
    except Exception:
        return ""


def extract_pdf_text_via_pypdf(path: Path) -> str:
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(str(path))
        return normalize_pdf_text("\n".join(page.extract_text() or "" for page in reader.pages))
    except Exception:
        return ""


def extract_pdf_text_via_ocr(path: Path, ocr_backend: OCRBackend) -> tuple[str, list[str]]:
    if not shutil.which("pdftoppm"):
        return "", ["pdftoppm not available for PDF OCR fallback"]

    page_texts: list[str] = []
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="kb-organizer-pdf-") as tmpdir:
        prefix = Path(tmpdir) / "page"
        completed = subprocess.run(
            ["pdftoppm", "-png", "-r", "200", str(path), str(prefix)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return "", [completed.stderr.strip() or "pdftoppm failed"]

        pages = sorted(Path(tmpdir).glob("page-*.png"))
        if not pages:
            return "", ["pdftoppm produced no rasterized pages"]

        for index, page_image in enumerate(pages, start=1):
            result = ocr_backend.extract(page_image)
            if result.status == "ok" and result.text:
                page_texts.append(f"## Page {index}\n\n{result.text.strip()}")
            elif result.status not in {"empty", "unavailable"}:
                errors.append(f"page {index}: {result.error or result.status}")
            elif result.status == "unavailable":
                errors.append(f"page {index}: OCR backend unavailable")
        return "\n\n".join(page_texts).strip(), errors


def normalize_pdf_text(text: str) -> str:
    return text.replace("\f", "\n\n").strip()


def pdf_has_meaningful_text(text: str, min_chars: int = 24) -> bool:
    visible_chars = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]", text)
    return len(visible_chars) >= min_chars


def extract_text_from_paddle_result(result: Any) -> str:
    lines: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"text", "rec_text", "transcription"} and isinstance(value, str):
                    cleaned = clean_text(value)
                    if cleaned:
                        lines.append(cleaned)
                elif key == "rec_texts" and isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            cleaned = clean_text(item)
                            if cleaned:
                                lines.append(cleaned)
                else:
                    walk(value)
            return

        if isinstance(node, (list, tuple)):
            if len(node) == 2 and isinstance(node[0], str) and isinstance(node[1], (int, float)):
                cleaned = clean_text(node[0])
                if cleaned:
                    lines.append(cleaned)
                return
            for item in node:
                walk(item)

    walk(result)
    return "\n".join(dedupe(lines))


def find_content_root(soup: BeautifulSoup) -> Tag:
    for selector in ["main", "article", "#content", ".content", ".main-content", "body"]:
        node = soup.select_one(selector)
        if node is not None:
            return node
    return soup


def html_list_to_markdown(tag: Tag, level: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * level + "- "
    for item in tag.find_all("li", recursive=False):
        text = clean_text(item.get_text(" ", strip=True))
        if text:
            lines.append(prefix + text)
        for nested in item.find_all(["ul", "ol"], recursive=False):
            nested_rendered = html_list_to_markdown(nested, level + 1)
            if nested_rendered:
                lines.append(nested_rendered)
    return "\n".join(lines)


def html_table_to_markdown(tag: Tag) -> str:
    rows = []
    for tr in tag.find_all("tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    lines = [
        "| " + " | ".join(rows[0]) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def generate_data_structure(directory: str, docs: list[DocumentRecord], child_dirs: list[str]) -> str:
    title = directory or "normalized"
    lines = [f"# {title}", "", "## Purpose"]
    lines.append(
        f"This directory contains normalized retrieval documents for `{directory}`."
        if directory else
        "This directory contains normalized retrieval documents at the root of the package."
    )
    lines.append("")
    if child_dirs:
        lines.append("## Subdirectories")
        for child in child_dirs:
            lines.append(f"- `{child}/`")
        lines.append("")
    if docs:
        lines.append("## Files")
        for doc in sorted(docs, key=lambda item: item.normalized_path):
            lines.append(f"- `{Path(doc.normalized_path).name}` — {doc.summary or 'See document body.'}")
        lines.append("")
    lines.append("## Coverage")
    lines.append(f"- Documents: {len(docs)}")
    if docs:
        lines.append(f"- Source types: {', '.join(sorted({doc.source_type for doc in docs}))}")
    lines.append("")
    return "\n".join(lines)


def generate_root_data_structure(documents: list[DocumentRecord], images: list[ImageRecord]) -> str:
    domains = Counter(doc.domain for doc in documents)
    lines = [
        "# Organized Knowledge Base",
        "",
        "## Purpose",
        "This package contains normalized retrieval documents, preserved originals, manifests, and image OCR sidecars produced by `knowledge-base-organizer`.",
        "",
        "## Topical Coverage",
    ]
    if domains:
        for domain, count in sorted(domains.items()):
            lines.append(f"- `{domain}` — {count} document(s)")
    else:
        lines.append("- No documents were normalized.")
    lines.extend([
        "",
        "## Image Coverage",
        f"- Images preserved: {len(images)}",
        f"- OCR successes: {sum(1 for image in images if image.ocr_status == 'ok')}",
        f"- OCR unavailable/failed: {sum(1 for image in images if image.ocr_status in {'failed', 'unavailable'})}",
        "",
        "## Retrieval Notes",
        "- Use `manifest.json` for document-level retrieval.",
        "- Use `image_manifest.json` for image-aware retrieval and OCR hits.",
        "- Use `normalized/**/data_structure.md` for hierarchical navigation.",
        "",
    ])
    return "\n".join(lines)


def resolve_resource_uri(source_uri: str, resource: str, local_base: Path | None) -> str:
    if local_base is not None and not re.match(r"^[a-zA-Z]+://", resource):
        return str((local_base / resource).resolve())
    return urllib.parse.urljoin(source_uri, resource)


def web_original_rel(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        parts = ["index"]
    if "." not in parts[-1]:
        parts[-1] += ".html"
    return str(Path(parsed.netloc, *parts))


def web_normalized_rel(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    parts = [slugify(part) for part in parsed.path.split("/") if part]
    if not parts:
        parts = ["index"]
    return str(Path(*parts).with_suffix(".md"))


def web_domain_name(url: str) -> str:
    rel = Path(web_normalized_rel(url))
    return rel.parent.as_posix() if rel.parent.as_posix() != "." else "root"


def strip_fragment(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(parsed._replace(fragment=""))


def image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(path) as image:
            return image.width, image.height
    except Exception:
        return None, None


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def slugify(value: str) -> str:
    value = urllib.parse.unquote(value).strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff._-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "item"


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: str) -> str:
    value = html.unescape(value).replace("\u200b", " ").replace("\ufeff", " ")
    return re.sub(r"\s+", " ", value).strip()


def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", value.lower())


def extract_keywords(text: str, limit: int = 10) -> list[str]:
    counter = Counter(token for token in tokenize(text) if token not in STOPWORDS and len(token) > 1)
    return [token for token, _ in counter.most_common(limit)]


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def relative_ref_to_image(image_path: str | None, doc_rel: Path) -> str | None:
    if not image_path:
        return None
    return os.path.relpath(Path(image_path), Path("normalized") / doc_rel.parent)


def main() -> None:
    args = parse_args()
    organizer = Organizer(args)
    organizer.run()
    print(f"Organized knowledge base written to {organizer.output_dir}")


if __name__ == "__main__":
    main()
