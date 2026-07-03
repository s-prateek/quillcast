from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from shared.config import enabled_platforms, load_platforms_config, load_topics_config
from shared.drafts import draft_targets_for_platforms, put_record
from shared.llm import generate_content_variants
from shared.models import PostRecord
from shared.rss import fetch_articles

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _select_topic(
    platforms_config: dict[str, Any],
    topics_config: dict[str, Any],
) -> tuple[str, str, str]:
    articles = fetch_articles(platforms_config)
    if articles:
        article = articles[0]
        return article.title, article.url, "rss"

    evergreen = topics_config.get("evergreen_topics", [])
    if not evergreen:
        raise RuntimeError("No RSS articles and no evergreen topics configured")

    topic = random.choice(evergreen)
    return topic, "", "evergreen"


def _topic_label_from_idea(idea: str, title: str | None = None) -> str:
    if title and title.strip():
        return title.strip()
    first_line = idea.strip().split("\n")[0]
    if len(first_line) <= 80:
        return first_line
    return first_line[:77] + "…"


def generate_post_for_topic(
    *,
    topic: str,
    source_url: str = "",
    source_type: str = "rss",
    content: str | None = None,
) -> dict[str, Any]:
    """LLM call #2 — generate platform variants for a user-selected topic."""
    platforms_config = load_platforms_config()
    topics_config = load_topics_config()
    platforms = enabled_platforms(platforms_config)
    if not platforms:
        raise RuntimeError("No platforms are enabled in config/platforms.yaml")

    voice = topics_config.get("voice", {})
    llm_topic = content if content is not None else topic
    content_variants = generate_content_variants(
        topic=llm_topic,
        source_url=source_url or ("custom" if source_type == "custom" else "evergreen"),
        source_type=source_type,
        enabled_platforms=platforms,
        voice=voice,
    )

    now = _utc_now()
    record = PostRecord(
        PostID=str(uuid.uuid4()),
        CreatedAt=now,
        UpdatedAt=now,
        Topic=topic,
        SourceURL=source_url,
        SourceType=source_type,
        OverallStatus="PENDING",
        ContentVariants=content_variants,
        Targets=draft_targets_for_platforms(platforms),
    )
    put_record(record)

    logger.info("Created draft %s for topic %r", record.PostID, record.Topic)
    return {
        "post_id": record.PostID,
        "topic": record.Topic,
        "source_type": record.SourceType,
        "platforms": platforms,
    }


def generate_post_from_idea(*, idea: str, title: str | None = None) -> dict[str, Any]:
    """Generate platform variants from the author's own idea (no RSS/discovery step)."""
    idea = idea.strip()
    if not idea:
        raise RuntimeError("Idea cannot be empty")
    return generate_post_for_topic(
        topic=_topic_label_from_idea(idea, title),
        source_url="",
        source_type="custom",
        content=idea,
    )


def generate_post() -> dict[str, Any]:
    """CLI convenience — auto-picks the newest RSS article or a random evergreen topic."""
    platforms_config = load_platforms_config()
    topics_config = load_topics_config()
    topic, source_url, source_type = _select_topic(platforms_config, topics_config)
    return generate_post_for_topic(
        topic=topic,
        source_url=source_url,
        source_type=source_type,
    )
