"""Data models used across the newsletter workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(slots=True)
class ArticleRecord:
    """Represents a single article entry in the newsletter."""

    title: str
    url: str
    content: str
    author_info: str
    category: str
    recommendation: str
    subcategory: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class NewsletterConfig:
    """Runtime configuration for newsletter generation."""

    input_path: Path
    output_path: Path
    request_timeout: float = 30.0
    max_retries: int = 2
    max_recommendation_words: int = 100


@dataclass(slots=True)
class NewsletterOutput:
    """Structured result ready for rendering."""

    articles_by_category: Dict[str, List[ArticleRecord]]
