#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree as ET

import markdown
import yaml
from weasyprint import HTML


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
TEMPLATES_DIR = ROOT / "templates"
DIST_DIR = ROOT / "dist"
ARTICLES_DIR = DIST_DIR / "articles"
PDF_DIR = DIST_DIR / "pdf"
CSS_PATH = TEMPLATES_DIR / "reader.css"


@dataclass(frozen=True)
class Document:
    source_path: Path
    slug: str
    title: str
    date: date
    tags: list[str]
    body: str
    html: str
    html_path: Path
    pdf_path: Path


def parse_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", raw, re.DOTALL)
    if not match:
        return {}, raw

    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata, match.group(2)


def parse_date(value: Any, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.strip()).date()
    return fallback


def title_from_body(body: str) -> str | None:
    for line in body.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1)
    return None


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", ascii_value).strip("-._").lower()
    if slug:
        return slug
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"doc-{digest}"


def render_article_page(title: str, published: date, article_html: str, css: str) -> str:
    escaped_title = html.escape(title)
    escaped_date = html.escape(published.isoformat())
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
{css}
  </style>
</head>
<body>
  <main class="page">
    <article>
      <header>
        <h1>{escaped_title}</h1>
        <div class="meta">{escaped_date}</div>
      </header>
      {article_html}
    </article>
  </main>
</body>
</html>
"""


def read_documents() -> list[Document]:
    css = CSS_PATH.read_text(encoding="utf-8")
    documents: list[Document] = []

    for source_path in sorted(DOCS_DIR.glob("*.md")):
        raw = source_path.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(raw)
        fallback_date = datetime.fromtimestamp(source_path.stat().st_mtime, timezone.utc).date()
        published = parse_date(metadata.get("date"), fallback_date)
        title = str(metadata.get("title") or title_from_body(body) or source_path.stem)
        tags = metadata.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        tags = [str(tag) for tag in tags]

        slug = slugify(source_path.stem)
        article_html = markdown.markdown(
            body,
            extensions=["extra", "sane_lists", "toc"],
            output_format="html5",
        )
        page_html = render_article_page(title, published, article_html, css)

        documents.append(
            Document(
                source_path=source_path,
                slug=slug,
                title=title,
                date=published,
                tags=tags,
                body=body,
                html=page_html,
                html_path=ARTICLES_DIR / f"{slug}.html",
                pdf_path=PDF_DIR / f"{slug}.pdf",
            )
        )

    return sorted(documents, key=lambda document: document.date, reverse=True)


def url_join(base_url: str, *parts: str) -> str:
    base = base_url.rstrip("/")
    encoded_parts = [quote(part.strip("/")) for part in parts if part]
    return "/".join([base, *encoded_parts])


def write_index(documents: list[Document], site_title: str, site_url: str) -> None:
    items = "\n".join(
        f"""      <li>
        <a href="articles/{html.escape(document.html_path.name)}">{html.escape(document.title)}</a>
        <span>{document.date.isoformat()}</span>
        <a href="pdf/{html.escape(document.pdf_path.name)}">PDF</a>
      </li>"""
        for document in documents
    )
    index_html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(site_title)}</title>
  <style>
    body {{
      margin: 0;
      color: #111;
      background: #f7f7f3;
      font-family: "Noto Serif CJK SC", "Noto Serif CJK", serif;
      line-height: 1.6;
    }}
    main {{
      max-width: 760px;
      margin: 0 auto;
      padding: 40px 24px;
    }}
    h1 {{
      margin: 0 0 8px;
    }}
    .feed {{
      margin-bottom: 28px;
    }}
    ul {{
      list-style: none;
      padding: 0;
    }}
    li {{
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 16px;
      padding: 14px 0;
      border-top: 1px solid #d7d7d0;
    }}
    a {{
      color: #111;
    }}
    span {{
      color: #555;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(site_title)}</h1>
    <p class="feed"><a href="{html.escape(url_join(site_url, "feed.xml"))}">RSS Feed</a></p>
    <ul>
{items}
    </ul>
  </main>
</body>
</html>
"""
    (DIST_DIR / "index.html").write_text(index_html, encoding="utf-8")


def write_rss(documents: list[Document], site_title: str, site_description: str, site_url: str) -> None:
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = site_title
    ET.SubElement(channel, "link").text = site_url.rstrip("/") + "/"
    ET.SubElement(channel, "description").text = site_description
    ET.SubElement(channel, "language").text = "zh-CN"

    if documents:
        latest = datetime.combine(documents[0].date, datetime.min.time(), tzinfo=timezone.utc)
        ET.SubElement(channel, "lastBuildDate").text = format_datetime(latest)

    for document in documents:
        item = ET.SubElement(channel, "item")
        html_url = url_join(site_url, "articles", document.html_path.name)
        pdf_url = url_join(site_url, "pdf", document.pdf_path.name)
        published = datetime.combine(document.date, datetime.min.time(), tzinfo=timezone.utc)

        ET.SubElement(item, "title").text = document.title
        ET.SubElement(item, "link").text = html_url
        ET.SubElement(item, "guid", isPermaLink="true").text = html_url
        ET.SubElement(item, "pubDate").text = format_datetime(published)
        ET.SubElement(item, "description").text = document.body[:500]
        ET.SubElement(
            item,
            "enclosure",
            url=pdf_url,
            length=str(document.pdf_path.stat().st_size),
            type="application/pdf",
        )
        for tag in document.tags:
            ET.SubElement(item, "category").text = tag

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(DIST_DIR / "feed.xml", encoding="utf-8", xml_declaration=True)


def build(site_title: str, site_description: str, site_url: str) -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    documents = read_documents()
    for document in documents:
        document.html_path.write_text(document.html, encoding="utf-8")
        HTML(string=document.html, base_url=str(ROOT)).write_pdf(document.pdf_path)

    write_index(documents, site_title, site_url)
    write_rss(documents, site_title, site_description, site_url)

    print(f"Built {len(documents)} document(s) into {DIST_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Markdown documents into HTML, PDF, and RSS.")
    parser.add_argument("--site-title", default="docs")
    parser.add_argument("--site-description", default="Markdown documents for e-ink reading.")
    parser.add_argument("--site-url", default="http://localhost:8000")
    args = parser.parse_args()

    build(args.site_title, args.site_description, args.site_url)


if __name__ == "__main__":
    main()
