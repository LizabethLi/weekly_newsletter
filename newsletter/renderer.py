"""Renderer for newsletter output."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from .categorizer import CATEGORY_ORDER, CATEGORY_PAPERS
from .models import ArticleRecord, NewsletterOutput


def _render_entry(article: ArticleRecord) -> List[str]:
    return [
        f"- 标题：{article.title}",
        f"  链接：{article.url}",
        f"  作者机构：{article.author_info}",
        f"  推荐理由：{article.recommendation}",
        "",
    ]


def render_markdown(output: NewsletterOutput) -> str:
    """Render the structured newsletter as markdown text."""

    lines: List[str] = ["# Weekly Newsletter", ""]
    for category in CATEGORY_ORDER:
        entries = output.articles_by_category.get(category, [])
        if not entries:
            continue
        lines.append(f"## {category}")
        lines.append("")
        if category == CATEGORY_PAPERS:
            grouped: Dict[str, List[ArticleRecord]] = defaultdict(list)
            for article in entries:
                subgroup = article.subcategory or "综合"
                grouped[subgroup].append(article)
            for subcategory in sorted(grouped.keys()):
                lines.append(f"### {subcategory}")
                lines.append("")
                for article in grouped[subcategory]:
                    lines.extend(_render_entry(article))
        else:
            for article in entries:
                lines.extend(_render_entry(article))
        if lines[-1] != "":
            lines.append("")
    rendered = "\n".join(lines).strip()
    return rendered + "\n"


__all__ = ["render_markdown"]
