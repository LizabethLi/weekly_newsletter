"""Core workflow for generating the newsletter from CSV input."""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from typing import Dict, Iterable, List

from .author_extraction import extract_author_info
from .categorizer import (
    CATEGORY_PAPERS,
    categorize_article,
    assign_paper_subcategory,
)
from .fetcher import fetch_article_text, fetch_html
from .models import ArticleRecord, NewsletterConfig, NewsletterOutput
from .recommendation import build_recommendation

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


def _build_article(row: dict[str, str], config: NewsletterConfig) -> ArticleRecord:
    title = row["title"]
    url = row["url"]
    LOGGER.info("Fetching article: %s", title)
    content = fetch_article_text(url, timeout=config.request_timeout, max_retries=config.max_retries)
    try:
        html = fetch_html(url, timeout=config.request_timeout, max_retries=config.max_retries)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Failed to fetch raw HTML for %s: %s", url, exc)
        html = None
    author_info = extract_author_info(content, html=html)
    category = categorize_article(title, url, content)
    subcategory = assign_paper_subcategory(title, content) if category == CATEGORY_PAPERS else None
    recommendation = build_recommendation(title, content, max_words=config.max_recommendation_words)
    metadata = {}
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
    for row in _iter_csv_rows(str(config.input_csv)):
        try:
            record = _build_article(row, config)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to process '%s': %s", row["title"], exc)
            continue
        records.append(record)
    grouped = defaultdict(list)
    for record in records:
        grouped[record.category].append(record)
    return NewsletterOutput(articles_by_category=dict(grouped))


__all__ = ["run_workflow"]
