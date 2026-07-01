from __future__ import annotations

import logging
import re
from typing import Any

from shared.config import load_platforms_config, load_topics_config
from shared.llm import curate_topic_candidates
from shared.models import TopicCandidate
from shared.rss import Article, fetch_articles

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _fallback_from_articles(articles: list[Article], *, max_topics: int) -> list[TopicCandidate]:
    candidates: list[TopicCandidate] = []
    for index, article in enumerate(articles[:max_topics]):
        summary = _strip_html(article.summary)
        hook = summary[:200] + ("…" if len(summary) > 200 else "") if summary else article.title
        candidates.append(
            TopicCandidate(
                id=f"rss-{index}",
                title=article.title,
                hook=hook,
                source_url=article.url,
                source_type="rss",
            )
        )
    return candidates


def _fallback_from_evergreen(evergreen_topics: list[str], *, max_topics: int) -> list[TopicCandidate]:
    return [
        TopicCandidate(
            id=f"evergreen-{index}",
            title=topic,
            hook="Evergreen idea from your curated list.",
            source_url="",
            source_type="evergreen",
        )
        for index, topic in enumerate(evergreen_topics[:max_topics])
    ]


def discover_topics(*, use_llm: bool = True, max_topics: int = 8) -> list[TopicCandidate]:
    """
    Fetch RSS, then optionally curate with an LLM into post-worthy topic cards.
    Falls back to raw RSS titles or evergreen list if LLM is unavailable.
    """
    platforms_config = load_platforms_config()
    topics_config = load_topics_config()
    articles = fetch_articles(platforms_config)
    evergreen = topics_config.get("evergreen_topics", [])
    voice = topics_config.get("voice", {})

    if not articles and not evergreen:
        raise RuntimeError("No RSS articles and no evergreen topics configured")

    if use_llm:
        try:
            return curate_topic_candidates(
                articles=articles,
                evergreen_topics=evergreen,
                voice=voice,
                max_topics=max_topics,
            )
        except Exception as exc:
            logger.warning("Topic curation LLM failed, using fallback list: %s", exc)

    if articles:
        candidates = _fallback_from_articles(articles, max_topics=max_topics)
        if evergreen:
            candidates.extend(_fallback_from_evergreen(evergreen, max_topics=2))
        return candidates[:max_topics]

    return _fallback_from_evergreen(evergreen, max_topics=max_topics)
