"""Generate concise recommendation blurbs for newsletter entries."""

from __future__ import annotations

import re
from typing import Iterable, List

CONTRIBUTION_KEYWORDS = (
    "we propose",
    "we introduce",
    "we present",
    "this paper",
    "this work",
    "in this paper",
    "our approach",
    "we demonstrate",
    "we show",
    "the study",
)

CONFERENCE_KEYWORDS = {
    "NeurIPS": "NeurIPS",
    "ICLR": "ICLR",
    "ICML": "ICML",
    "CVPR": "CVPR",
    "ACL": "ACL",
    "EMNLP": "EMNLP",
    "KDD": "KDD",
    "AAAI": "AAAI",
    "IJCAI": "IJCAI",
}

GITHUB_PATTERN = re.compile(r"https?://github\.com/[\w\-/%.]+", re.IGNORECASE)
MODEL_PATTERN = re.compile(r"https?://(?:huggingface\.co|modelscope\.cn|civitai\.com|replicate\.com)/[\w\-/%.]+", re.IGNORECASE)
ATTACHMENT_TERMS = ("supplementary", "appendix", "additional material", "appendices")

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")


def _split_sentences(text: str) -> List[str]:
    """Split text into candidate sentences."""

    text = re.sub(r"\s+", " ", text)
    sentences = SENTENCE_SPLIT_RE.split(text)
    cleaned = [sentence.strip() for sentence in sentences if sentence and len(sentence.split()) >= 5]
    return cleaned[:20]


def _select_core_sentences(sentences: Iterable[str]) -> List[str]:
    selected: List[str] = []
    for sentence in sentences:
        lower = sentence.lower()
        if any(keyword in lower for keyword in CONTRIBUTION_KEYWORDS):
            selected.append(sentence)
        if len(selected) == 2:
            break
    if not selected:
        sentences_list = list(sentences)
        selected = sentences_list[:2]
    elif len(selected) < 2:
        for sentence in sentences:
            if sentence not in selected:
                selected.append(sentence)
            if len(selected) == 2:
                break
    return selected


def _collect_feature_sentences(text: str) -> List[str]:
    lower = text.lower()
    features: List[str] = []
    for token, label in CONFERENCE_KEYWORDS.items():
        if token.lower() in lower:
            features.append(f"收录于 {label}.")
            break
    github_links = GITHUB_PATTERN.findall(text)
    if github_links:
        features.append(f"GitHub: {github_links[0]}.")
    model_links = MODEL_PATTERN.findall(text)
    if model_links:
        features.append(f"模型链接：{model_links[0]}.")
    if any(term in lower for term in ATTACHMENT_TERMS):
        features.append("提供补充材料。")
    return features


def limit_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " ..."


def build_recommendation(title: str, content: str, max_words: int = 100) -> str:
    """Construct a recommendation blurb under the word limit."""

    paragraphs = content.splitlines()
    primary_text = " ".join(paragraphs[:20])
    sentences = _split_sentences(primary_text)
    if not sentences:
        sentences = [primary_text[:300]]
    selected_sentences = _select_core_sentences(sentences)
    core = " ".join(selected_sentences).strip()
    features = _collect_feature_sentences(content)
    summary = " ".join(sentence for sentence in [core, " ".join(features)] if sentence)
    summary = summary or f"Overview of {title}."
    return limit_words(summary, max_words)


__all__ = ["build_recommendation", "limit_words"]
