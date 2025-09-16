"""Categorization logic for newsletter entries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

CATEGORY_PAPERS = "论文 Papers"
CATEGORY_BLOGS = "博客 Blogs"
CATEGORY_ENGINEERING = "工程 / 产品 / 商业 Engineering & Product & Business"
CATEGORY_OPEN_SOURCE = "开源项目汇总 Open Source Roundup"

CATEGORY_ORDER = [
    CATEGORY_PAPERS,
    CATEGORY_BLOGS,
    CATEGORY_ENGINEERING,
    CATEGORY_OPEN_SOURCE,
]

PAPER_HOST_KEYWORDS = {
    "arxiv.org",
    "openreview.net",
    "papers.nips.cc",
    "proceedings.mlr.press",
    "dl.acm.org",
    "ieeexplore.ieee.org",
    "hal.science",
    "research.google",
    "static.googleusercontent.com",
    "neurips.cc",
    "iclr.cc",
}

OPEN_SOURCE_HOSTS = {
    "github.com",
    "gitlab.com",
    "huggingface.co",
    "modelscope.cn",
    "pytorch.org",
}

ENGINEERING_HOST_HINTS = {
    "openai.com",
    "deepmind.com",
    "googleblog.com",
    "blog.google",
    "meta.com",
    "engineering.fb.com",
    "anthropic.com",
    "microsoft.com",
    "azure.microsoft.com",
    "aws.amazon.com",
    "nvidia.com",
    "cohere.ai",
}

PAPER_KEYWORDS = [
    "preprint",
    "we propose",
    "this paper",
    "abstract",
    "experiments",
    "dataset",
    "state-of-the-art",
]

ENGINEERING_KEYWORDS = [
    "launch",
    "product",
    "roadmap",
    "platform",
    "pricing",
    "enterprise",
    "customers",
    "availability",
    "release",
]

OPEN_SOURCE_KEYWORDS = [
    "open source",
    "github",
    "apache",
    "mit license",
    "available on github",
]

@dataclass(frozen=True)
class PaperSubcategory:
    name: str
    keywords: tuple[str, ...]


PAPER_SUBCATEGORIES: tuple[PaperSubcategory, ...] = (
    PaperSubcategory("LLM", ("llm", "large language model", "language model", "gpt", "transformer")),
    PaperSubcategory("Agents", ("agent", "tool use", "tool-use", "autonomous", "planner", "workflow")),
    PaperSubcategory("多模态", ("multimodal", "vision-language", "vlm", "image", "video", "audio", "speech")),
    PaperSubcategory("RL", ("reinforcement learning", "rl ", "policy gradient", "ppo", "q-learning")),
    PaperSubcategory("系统/工程", ("system", "systems", "latency", "throughput", "compiler", "serving", "hardware", "scaling")),
    PaperSubcategory("检索/RAG", ("retrieval", "rag", "retriever", "vector database", "index", "memory")),
    PaperSubcategory("评测", ("benchmark", "evaluation", "evaluate", "assess", "metric")),
    PaperSubcategory("数据/合成数据", ("dataset", "data", "synthetic", "corpus", "data generation", "data-centric")),
    PaperSubcategory("安全/对齐", ("alignment", "aligned", "safety", "secure", "guardrail", "robust")),
)

EXTRA_SUBCATEGORY_RULES = (
    PaperSubcategory("机器人", ("robot", "robotics", "manipulation", "embodiment")),
    PaperSubcategory("医疗/生物", ("biomedical", "medical", "healthcare", "protein", "molecule")),
)


def _text_contains(text: str, keywords: Iterable[str]) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in keywords)


def is_paper(title: str, url: str, content: str) -> bool:
    host = urlparse(url).netloc.lower()
    if any(key in host for key in PAPER_HOST_KEYWORDS):
        return True
    combined = f"{title}\n{content}".lower()
    if "doi" in combined or "arxiv" in combined:
        return True
    return _text_contains(combined, PAPER_KEYWORDS)


def is_open_source(title: str, url: str, content: str) -> bool:
    host = urlparse(url).netloc.lower()
    if any(host.endswith(candidate) or candidate in host for candidate in OPEN_SOURCE_HOSTS):
        return True
    combined = f"{title}\n{content}".lower()
    if "github.com" in combined or _text_contains(combined, OPEN_SOURCE_KEYWORDS):
        return True
    return False


def is_engineering(title: str, url: str, content: str) -> bool:
    host = urlparse(url).netloc.lower()
    if any(host.endswith(candidate) or candidate in host for candidate in ENGINEERING_HOST_HINTS):
        return True
    combined = f"{title}\n{content}".lower()
    return _text_contains(combined, ENGINEERING_KEYWORDS)


def categorize_article(title: str, url: str, content: str) -> str:
    if is_paper(title, url, content):
        return CATEGORY_PAPERS
    if is_open_source(title, url, content):
        return CATEGORY_OPEN_SOURCE
    if is_engineering(title, url, content):
        return CATEGORY_ENGINEERING
    return CATEGORY_BLOGS


def assign_paper_subcategory(title: str, content: str) -> str:
    text = f"{title}\n{content}".lower()
    for rule in PAPER_SUBCATEGORIES + EXTRA_SUBCATEGORY_RULES:
        if _text_contains(text, rule.keywords):
            return rule.name
    # Heuristic for math/theory heavy work
    if re.search(r"theorem|proof|complexity", text):
        return "理论"
    return "综合"


__all__ = [
    "CATEGORY_PAPERS",
    "CATEGORY_BLOGS",
    "CATEGORY_ENGINEERING",
    "CATEGORY_OPEN_SOURCE",
    "CATEGORY_ORDER",
    "categorize_article",
    "assign_paper_subcategory",
]
