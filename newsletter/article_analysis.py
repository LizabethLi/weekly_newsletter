"""High-level LLM-powered analysis helpers for newsletter articles."""

from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass
from typing import Dict, Optional

from .categorizer import (
    CATEGORY_BLOGS,
    CATEGORY_ENGINEERING,
    CATEGORY_OPEN_SOURCE,
    CATEGORY_PAPERS,
)
from .llm_client import LLMError, get_llm_client

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ArticleAnalysis:
    """Structured interpretation of LLM results for an article."""

    category: str
    subcategory: Optional[str]
    recommendation: str
    category_reason: Optional[str]
    recommendation_reason: Optional[str]
    raw_response: Dict[str, object]


_CATEGORY_OVERVIEW = textwrap.dedent(
    """
    你是AI行业周报的编辑，需要阅读文章并决定它在周报的哪个板块中展示。
    板块仅限于以下四个之一：
    - papers: 学术论文、预印本、会议论文、严肃的研究报告。
    - blogs: 博客文章、访谈、短评、非正式总结。
    - engineering: 科技公司或团队发布的工程/产品/商业动态。
    - open_source: 开源代码、模型、数据集或工具的发布与更新。
    请只返回一个板块标签。
    """
)

_PROMPT_TEMPLATE = textwrap.dedent(
    """
    Title: {title}
    URL: {url}

    Use the article content below (may be truncated) to complete the task.
    ---
    {content}
    ---

    Output strict JSON (no markdown, no comments) with the following keys:
    - category: one of ["papers", "blogs", "engineering", "open_source"].
    - category_reason: concise Chinese sentence explaining the category choice.
    - subcategory: if category == "papers", generate a短小的中文子主题标签(<=8个汉字或字符); otherwise null.
    - recommendation: 1-2 concise Chinese sentences summarising why读者应该关注, 不超过 {max_words} 个英文单词数量上限 (约 {max_words} words) 的长度。
    - recommendation_reason: 提供一句中文或中英混合的话，说明推荐重点或贡献亮点，可与 recommendation 相同或补充细节。
    Ensure the JSON is valid and contains all keys even if some values are null.
    """
)

_CATEGORY_MAP = {
    "papers": CATEGORY_PAPERS,
    "paper": CATEGORY_PAPERS,
    "blogs": CATEGORY_BLOGS,
    "blog": CATEGORY_BLOGS,
    "engineering": CATEGORY_ENGINEERING,
    "product": CATEGORY_ENGINEERING,
    "open_source": CATEGORY_OPEN_SOURCE,
    "opensource": CATEGORY_OPEN_SOURCE,
}


def _prepare_content_excerpt(content: str, max_chars: int = 6000) -> str:
    snippet = " ".join(content.split())
    if len(snippet) > max_chars:
        return snippet[:max_chars] + " ..."
    return snippet


def analyze_article_with_llm(
    *,
    title: str,
    url: str,
    content: str,
    max_words: int,
    temperature: float = 0.1,
) -> ArticleAnalysis:
    """Call the configured LLM to classify and summarise an article."""

    client = get_llm_client()
    formatted_prompt = _PROMPT_TEMPLATE.format(
        title=title.strip(),
        url=url.strip(),
        content=_prepare_content_excerpt(content),
        max_words=max_words,
    )
    response = client.generate_json(
        formatted_prompt,
        system_instruction=_CATEGORY_OVERVIEW,
        temperature=temperature,
        max_output_tokens=2048,
    )

    raw_category = str(response.get("category", "")).strip().lower()
    category = _CATEGORY_MAP.get(raw_category, CATEGORY_BLOGS)
    if raw_category not in _CATEGORY_MAP:
        LOGGER.warning("LLM returned unknown category '%s' for '%s'", raw_category, title)
    subcategory_raw = response.get("subcategory")
    subcategory = None
    if category == CATEGORY_PAPERS:
        if isinstance(subcategory_raw, str) and subcategory_raw.strip():
            subcategory = subcategory_raw.strip()
        else:
            subcategory = "综合"
    recommendation = str(response.get("recommendation", "")).strip()
    if not recommendation:
        recommendation = "尚未生成推荐理由。"
    category_reason = _safe_get_str(response, "category_reason")
    recommendation_reason = _safe_get_str(response, "recommendation_reason")
    return ArticleAnalysis(
        category=category,
        subcategory=subcategory,
        recommendation=recommendation,
        category_reason=category_reason,
        recommendation_reason=recommendation_reason,
        raw_response=response,
    )


def _safe_get_str(payload: Dict[str, object], key: str) -> Optional[str]:
    value = payload.get(key)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def analyze_article_with_fallback(
    *,
    title: str,
    url: str,
    content: str,
    max_words: int,
) -> ArticleAnalysis:
    """Wrapper that surfaces LLM errors while keeping the workflow resilient."""

    try:
        return analyze_article_with_llm(
            title=title,
            url=url,
            content=content,
            max_words=max_words,
        )
    except LLMError as exc:
        LOGGER.error("LLM analysis failed for '%s': %s", title, exc)
        # Defer imports to avoid circular dependencies when used as fallback only.
        from .categorizer import assign_paper_subcategory, categorize_article
        from .recommendation import build_recommendation

        category = categorize_article(title=title, url=url, content=content)
        subcategory = None
        if category == CATEGORY_PAPERS:
            subcategory = assign_paper_subcategory(title=title, content=content)
        recommendation = build_recommendation(title=title, content=content, max_words=max_words)
        return ArticleAnalysis(
            category=category,
            subcategory=subcategory,
            recommendation=recommendation,
            category_reason=f"LLM fallback: {exc}",
            recommendation_reason="自动规则生成。",
            raw_response={"fallback": True, "error": str(exc)},
        )


__all__ = ["ArticleAnalysis", "analyze_article_with_fallback"]
