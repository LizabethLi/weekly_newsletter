"""Heuristics for extracting author and institution information."""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Set

from bs4 import BeautifulSoup

META_AUTHOR_KEYS = {
    "author",
    "article:author",
    "byline",
    "dc.creator",
    "dcterms.creator",
    "parsely-author",
}

META_INSTITUTION_KEYS = {
    "article:publisher",
    "publisher",
    "og:site_name",
    "organization",
    "company",
}

INSTITUTION_PATTERNS = [
    re.compile(r"([A-Z][\w&\-.]+(?:\s+[A-Z][\w&\-.]+)*\s+(?:University|Institute|Laboratories|Labs|Research|AI|School|College|Center))"),
    re.compile(r"([A-Z][\w&\-.]+(?:\s+[A-Z][\w&\-.]+)*\s+(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Corporation|Technologies|Systems|Analytics))"),
    re.compile(r"(OpenAI|Anthropic|DeepMind|Google Research|Meta AI|Microsoft Research|Amazon|NVIDIA|Tencent|Baidu|Huawei)", re.IGNORECASE),
]

ARXIV_AUTHOR_RE = re.compile(r"^Authors?:\s*(?P<value>.+)$", re.IGNORECASE)
AFFILIATION_RE = re.compile(r"^Affiliations?:\s*(?P<value>.+)$", re.IGNORECASE)
BYLINE_RE = re.compile(r"^(?:By|by)\s+(.+)$")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ;,|\u3001")


def _split_values(value: str) -> List[str]:
    parts = re.split(r"(?:,|;|/|\band\b|\u3001|\u2013)", value, flags=re.IGNORECASE)
    return [_clean(part) for part in parts if _clean(part)]


def _dedupe(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for value in values:
        normalized = value.lower()
        if normalized not in seen:
            seen.add(normalized)
            result.append(value)
    return result


def _meta_values(soup: BeautifulSoup, keys: Set[str]) -> List[str]:
    results: List[str] = []
    for meta in soup.find_all("meta"):
        for attr in ("name", "property", "itemprop"):
            key = meta.get(attr)
            if not key:
                continue
            if key.lower() in keys:
                content = meta.get("content") or meta.get("value")
                if content:
                    results.extend(_split_values(content))
    return results


def _extract_from_byline(soup: BeautifulSoup) -> List[str]:
    values: List[str] = []
    for tag in soup.find_all(True, class_=re.compile("author|byline", re.IGNORECASE)):
        text = tag.get_text(separator=" ", strip=True)
        if text:
            match = BYLINE_RE.match(text)
            if match:
                values.extend(_split_values(match.group(1)))
            else:
                values.extend(_split_values(text))
    for tag in soup.find_all("a", attrs={"rel": "author"}):
        text = tag.get_text(separator=" ", strip=True)
        if text:
            values.extend(_split_values(text))
    return values


def _extract_arxiv_info(text_lines: Sequence[str]) -> tuple[list[str], list[str]]:
    authors: List[str] = []
    affiliations: List[str] = []
    for line in text_lines[:40]:
        author_match = ARXIV_AUTHOR_RE.match(line)
        if author_match:
            authors.extend(_split_values(author_match.group("value")))
        affiliation_match = AFFILIATION_RE.match(line)
        if affiliation_match:
            affiliations.extend(_split_values(affiliation_match.group("value")))
    return authors, affiliations


def _extract_institutions_from_text(text: str) -> List[str]:
    snippet = text[:4000]
    found: Set[str] = set()
    for pattern in INSTITUTION_PATTERNS:
        for match in pattern.findall(snippet):
            value = _clean(match if isinstance(match, str) else match[0])
            if 2 <= len(value.split()) <= 10:
                found.add(value)
    # Look for explicit phrases like "from X" in the opening paragraphs
    intro = "\n".join(text.splitlines()[:20])
    for match in re.findall(r"from ([A-Z][\w\s&-]+(?:University|Institute|Research|Labs|Lab))", intro):
        value = _clean(match)
        if value:
            found.add(value)
    return sorted(found)


def extract_author_info(article_text: str, html: str | None = None) -> str:
    """Return a concise author/institution string extracted from content."""

    text_lines = [line.strip() for line in article_text.splitlines() if line.strip()]
    authors: List[str] = []
    institutions: List[str] = []

    arxiv_authors, arxiv_affiliations = _extract_arxiv_info(text_lines)
    authors.extend(arxiv_authors)
    institutions.extend(arxiv_affiliations)

    if html:
        soup = BeautifulSoup(html, "html.parser")
        authors.extend(_meta_values(soup, META_AUTHOR_KEYS))
        authors.extend(_extract_from_byline(soup))
        institutions.extend(_meta_values(soup, META_INSTITUTION_KEYS))

    # Additional heuristics from plain text
    if not authors:
        for line in text_lines[:10]:
            match = BYLINE_RE.match(line)
            if match:
                authors.extend(_split_values(match.group(1)))
                break

    if not institutions:
        institutions.extend(_extract_institutions_from_text(article_text))

    authors = _dedupe(authors)
    institutions = _dedupe(institutions)

    if authors and institutions:
        return f"{'；'.join(authors)}（{'，'.join(institutions)}）"
    if authors:
        return "；".join(authors)
    if institutions:
        return "，".join(institutions)
    return "未注明"
