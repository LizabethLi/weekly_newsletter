"""Core workflow for generating the newsletter from CSV or text input."""

from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .article_analysis import analyze_article_with_fallback
from .author_extraction import extract_author_info
from .categorizer import CATEGORY_PAPERS
from .fetcher import fetch_article_text, fetch_html
from .models import ArticleRecord, NewsletterConfig, NewsletterOutput

LOGGER = logging.getLogger(__name__)

_TITLE_COLUMNS = {"title", "标题", "name"}
_URL_COLUMNS = {"url", "链接", "link"}


def _resolve_column(fieldnames: Iterable[str], candidates: set[str]) -> str:
    lower_to_original: Dict[str, str] = {name.lower(): name for name in fieldnames}
    for candidate in candidates:
        if candidate.lower() in lower_to_original:
            return lower_to_original[candidate.lower()]
    raise KeyError(f"Missing required column. Expected one of: {sorted(candidates)}")


def _iter_csv_rows(path: str) -> Iterable[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("CSV must include a header row")
        title_column = _resolve_column(reader.fieldnames, _TITLE_COLUMNS)
        url_column = _resolve_column(reader.fieldnames, _URL_COLUMNS)
        for row in reader:
            title = (row.get(title_column) or "").strip()
            url = (row.get(url_column) or "").strip()
            if not title or not url:
                LOGGER.warning("Skipping row with missing title or url: %s", row)
                continue
            yield {"title": title, "url": url}


def _iter_txt_urls(path: str) -> Iterable[dict[str, str]]:
    with open(path, "r", encoding="utf-8") as txt_file:
        for line in txt_file:
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            yield {"url": url}


def _iter_input_rows(path: str) -> Iterable[dict[str, str]]:
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        yield from _iter_csv_rows(path)
    else:
        yield from _iter_txt_urls(path)


def _clean_title(value: str) -> str:
    cleaned = " ".join(value.split()).strip("-–—|·• ")
    return cleaned[:200]


def _infer_title(*, url: str, html: str | None, content: str) -> str:
    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:  # noqa: BLE001
            soup = None
        if soup:
            if soup.title and soup.title.string:
                candidate = _clean_title(soup.title.string)
                if candidate:
                    return candidate
            heading = soup.find("h1")
            if heading:
                text = _clean_title(heading.get_text(separator=" ", strip=True))
                if text:
                    return text
    for index, line in enumerate(content.splitlines()):
        if index > 40:
            break
        if not line.strip():
            continue
        text = _clean_title(line)
        if text:
            return text
    parsed = urlparse(url)
    last_segment = parsed.path.rstrip("/").split("/")[-1]
    if last_segment:
        fallback = last_segment.replace("-", " ").replace("_", " ")
        fallback = _clean_title(fallback)
        if fallback:
            return fallback
    if parsed.netloc:
        return parsed.netloc
    return url


def _build_article(row: dict[str, str], config: NewsletterConfig) -> ArticleRecord:
    supplied_title = row.get("title")
    url = row["url"]
    LOGGER.info("Fetching article: %s", supplied_title or url)
    content = fetch_article_text(url, timeout=config.request_timeout, max_retries=config.max_retries)
    try:
        html = fetch_html(url, timeout=config.request_timeout, max_retries=config.max_retries)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Failed to fetch raw HTML for %s: %s", url, exc)
        html = None
    author_info = extract_author_info(content, html=html)
    title = supplied_title or _infer_title(url=url, html=html, content=content)
    analysis = analyze_article_with_fallback(
        title=title,
        url=url,
        content=content,
        max_words=config.max_recommendation_words,
    )
    category = analysis.category
    subcategory = analysis.subcategory if category == CATEGORY_PAPERS else None
    recommendation = analysis.recommendation
    metadata: Dict[str, str] = {}
    if analysis.category_reason:
        metadata["category_reason"] = analysis.category_reason
    if analysis.recommendation_reason:
        metadata["recommendation_reason"] = analysis.recommendation_reason
    if analysis.raw_response:
        try:
            metadata["llm_raw"] = json.dumps(analysis.raw_response, ensure_ascii=False)
        except TypeError:
            metadata["llm_raw"] = "{\"error\": \"unserializable response\"}"
    return ArticleRecord(
        title=title,
        url=url,
        content=content,
        author_info=author_info,
        category=category,
        recommendation=recommendation,
        subcategory=subcategory,
        metadata=metadata,
    )


def run_workflow(config: NewsletterConfig) -> NewsletterOutput:
    records: List[ArticleRecord] = []
    for row in _iter_input_rows(str(config.input_path)):
        try:
            record = _build_article(row, config)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to process '%s': %s", row.get("title") or row.get("url"), exc)
            continue
        records.append(record)
    grouped = defaultdict(list)
    for record in records:
        grouped[record.category].append(record)
    return NewsletterOutput(articles_by_category=dict(grouped))


__all__ = ["run_workflow"]
