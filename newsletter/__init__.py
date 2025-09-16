"""Utilities for generating categorized AI newsletters."""

from .models import ArticleRecord, NewsletterConfig, NewsletterOutput
from .cli import main

__all__ = ["ArticleRecord", "NewsletterConfig", "NewsletterOutput", "main"]
