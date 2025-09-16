"""Network helpers for retrieving article content and metadata."""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Optional
from urllib.parse import ParseResult, urlparse, urlunparse

import requests
from requests import Response

DEFAULT_HEADERS = {
    "User-Agent": (
        "weekly-newsletter-bot/0.1 (+https://github.com/) "
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    )
}


def normalize_url(url: str) -> str:
    """Ensure the URL has a scheme and strip whitespace."""

    url = url.strip()
    if not url:
        raise ValueError("URL is empty")
    parsed = urlparse(url, scheme="https")
    if not parsed.netloc:
        # assume the whole string is a hostname
        parsed = parsed._replace(netloc=parsed.path, path="")
    if parsed.scheme not in {"http", "https"}:
        parsed = parsed._replace(scheme="https")
    return urlunparse(parsed)


def _to_jina_reader_url(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    target = ParseResult(
        scheme=parsed.scheme,
        netloc=parsed.netloc,
        path=parsed.path,
        params="",
        query=parsed.query,
        fragment=parsed.fragment,
    )
    normalized = urlunparse(target)
    return f"https://r.jina.ai/{normalized}"


def _fetch(url: str, timeout: float, max_retries: int) -> Response:
    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS)
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == max_retries:
                break
            backoff = min(2**attempt * 0.5, 5.0)
            time.sleep(backoff)
    assert last_error is not None
    raise last_error


@lru_cache(maxsize=128)
def fetch_article_text(url: str, timeout: float = 30.0, max_retries: int = 2) -> str:
    """Retrieve article text via the Jina Reader service."""

    jina_url = _to_jina_reader_url(url)
    response = _fetch(jina_url, timeout=timeout, max_retries=max_retries)
    return response.text


@lru_cache(maxsize=128)
def fetch_html(url: str, timeout: float = 30.0, max_retries: int = 2) -> str:
    """Retrieve the original HTML page for metadata extraction."""

    normalized = normalize_url(url)
    response = _fetch(normalized, timeout=timeout, max_retries=max_retries)
    response.encoding = response.encoding or response.apparent_encoding
    return response.text
