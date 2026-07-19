from __future__ import annotations

import logging
import re

from shared.config import (
    get_persona,
    load_platforms_config,
    persona_voice_for_llm,
    rss_feeds_for_persona,
)
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


def discover_topics(
    *,
    persona_id: str,
    use_llm: bool = True,
    max_topics: int | None = None,
    exclude_titles: list[str] | None = None,
) -> list[TopicCandidate]:
    """
    Fetch persona-specific RSS, then optionally curate with an LLM into topic cards.
    Falls back to raw RSS titles or evergreen list if LLM is unavailable.
    """
    platforms_config = load_platforms_config()
    rss_filter = platforms_config.get("rss_filter", {})
    if max_topics is None:
        max_topics = int(rss_filter.get("max_topics_per_run", 12))

    persona = get_persona(persona_id)
    feeds = rss_feeds_for_persona(persona_id)
    articles = fetch_articles(platforms_config, feed_configs=feeds)
    evergreen = persona.get("evergreen_topics", [])
    voice = persona_voice_for_llm(persona)

    if not articles and not evergreen:
        raise RuntimeError("No RSS articles and no evergreen topics configured for this persona")

    if use_llm:
        try:
            return curate_topic_candidates(
                articles=articles,
                evergreen_topics=evergreen,
                voice=voice,
                persona=persona,
                max_topics=max_topics,
                exclude_titles=exclude_titles,
            )
        except Exception as exc:
            logger.warning("Topic curation LLM failed, using fallback list: %s", exc)

    excluded = {title.strip().lower() for title in (exclude_titles or []) if title.strip()}
    if articles:
        candidates = _fallback_from_articles(articles, max_topics=max_topics)
        candidates = [candidate for candidate in candidates if candidate.title.lower() not in excluded]
        if evergreen:
            evergreen_candidates = _fallback_from_evergreen(evergreen, max_topics=2)
            evergreen_candidates = [
                candidate
                for candidate in evergreen_candidates
                if candidate.title.lower() not in excluded
            ]
            candidates.extend(evergreen_candidates)
        return candidates[:max_topics]

    return [
        candidate
        for candidate in _fallback_from_evergreen(evergreen, max_topics=max_topics)
        if candidate.title.lower() not in excluded
    ]
