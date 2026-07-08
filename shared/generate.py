from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from shared.config import (
    enabled_platforms,
    get_default_persona_id,
    get_persona,
    load_platforms_config,
    persona_voice_for_llm,
    resolve_persona_id,
    rss_feeds_for_persona,
)
from shared.drafts import draft_targets_for_platforms, get_record, put_record
from shared.llm import generate_content_variants
from shared.models import PostRecord
from shared.rss import fetch_articles

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _blog_default_tags(persona: dict[str, Any]) -> list[str]:
    defaults = persona.get("blog_defaults") or {}
    tags = defaults.get("tags") or []
    if isinstance(tags, list):
        return [str(tag).strip() for tag in tags if str(tag).strip()]
    return []


def _merge_blog_tags(content_variants: dict[str, Any], default_tags: list[str]) -> None:
    blog = content_variants.get("blog")
    if not isinstance(blog, dict) or not default_tags:
        return
    existing = blog.get("tags") or []
    if not isinstance(existing, list):
        existing = []
    merged: list[str] = []
    for tag in [*default_tags, *existing]:
        cleaned = str(tag).strip()
        if cleaned and cleaned not in merged:
            merged.append(cleaned)
    blog["tags"] = merged


def _select_topic(
    platforms_config: dict[str, Any],
    persona_id: str,
) -> tuple[str, str, str]:
    feeds = rss_feeds_for_persona(persona_id)
    articles = fetch_articles(platforms_config, feed_configs=feeds)
    if articles:
        article = articles[0]
        return article.title, article.url, "rss"

    persona = get_persona(persona_id)
    evergreen = persona.get("evergreen_topics", [])
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


def _generate_variants_for_persona(
    *,
    persona_id: str,
    topic: str,
    source_url: str,
    source_type: str,
    content: str | None = None,
    personality_boost: bool = False,
) -> dict[str, Any]:
    platforms_config = load_platforms_config()
    platforms = enabled_platforms(platforms_config)
    if not platforms:
        raise RuntimeError("No platforms are enabled in config/platforms.yaml")

    persona = get_persona(persona_id)
    voice = persona_voice_for_llm(persona)
    llm_topic = content if content is not None else topic
    variants = generate_content_variants(
        topic=llm_topic,
        source_url=source_url or ("custom" if source_type == "custom" else "evergreen"),
        source_type=source_type,
        enabled_platforms=platforms,
        voice=voice,
        personality_boost=personality_boost,
        blog_default_tags=_blog_default_tags(persona),
    )
    _merge_blog_tags(variants, _blog_default_tags(persona))
    _embed_pull_quote(variants)
    return variants


def _embed_pull_quote(content_variants: dict[str, Any]) -> None:
    blog = content_variants.get("blog")
    if not isinstance(blog, dict):
        return
    pull = str(blog.get("pull_quote", "")).strip()
    body = str(blog.get("body", "")).strip()
    if pull and pull not in body:
        blog["body"] = f"> {pull}\n\n{body}".strip()


def generate_post_for_topic(
    *,
    topic: str,
    source_url: str = "",
    source_type: str = "rss",
    content: str | None = None,
    persona_id: str | None = None,
) -> dict[str, Any]:
    """LLM call #2 — generate platform variants for a user-selected topic."""
    pid = resolve_persona_id(persona_id)
    content_variants = _generate_variants_for_persona(
        persona_id=pid,
        topic=topic,
        source_url=source_url,
        source_type=source_type,
        content=content,
    )

    now = _utc_now()
    record = PostRecord(
        PostID=str(uuid.uuid4()),
        CreatedAt=now,
        UpdatedAt=now,
        Topic=topic,
        SourceURL=source_url,
        SourceType=source_type,
        SourceContent=content or "" if source_type == "custom" else "",
        PersonaID=pid,
        OverallStatus="PENDING",
        ContentVariants=content_variants,
        Targets=draft_targets_for_platforms(enabled_platforms(load_platforms_config())),
    )
    put_record(record)

    logger.info("Created draft %s for topic %r (persona=%s)", record.PostID, record.Topic, pid)
    return {
        "post_id": record.PostID,
        "topic": record.Topic,
        "source_type": record.SourceType,
        "persona_id": record.PersonaID,
        "platforms": list(record.Targets.keys()),
    }


def generate_post_from_idea(
    *,
    idea: str,
    title: str | None = None,
    persona_id: str | None = None,
) -> dict[str, Any]:
    """Generate platform variants from the author's own idea (no RSS/discovery step)."""
    idea = idea.strip()
    if not idea:
        raise RuntimeError("Idea cannot be empty")
    return generate_post_for_topic(
        topic=_topic_label_from_idea(idea, title),
        source_url="",
        source_type="custom",
        content=idea,
        persona_id=persona_id,
    )


def regenerate_draft_content(*, post_id: str, personality_boost: bool = True) -> dict[str, Any]:
    """Re-run LLM generation for an existing draft; clears per-platform edits."""
    record = get_record(post_id)
    if record is None:
        raise RuntimeError(f"Draft not found: {post_id}")

    content = record.SourceContent if record.SourceType == "custom" and record.SourceContent else None
    variants = _generate_variants_for_persona(
        persona_id=resolve_persona_id(record.PersonaID),
        topic=record.Topic,
        source_url=record.SourceURL,
        source_type=record.SourceType,
        content=content,
        personality_boost=personality_boost,
    )

    record.ContentVariants = variants
    for target in record.Targets.values():
        target.EditedContent = None
        if target.Status == "DRAFT":
            target.ErrorLog = None
    record.UpdatedAt = _utc_now()
    put_record(record)

    return {"post_id": post_id, "persona_id": record.PersonaID}


def generate_post(*, persona_id: str | None = None) -> dict[str, Any]:
    """CLI convenience — auto-picks the newest RSS article or a random evergreen topic."""
    pid = resolve_persona_id(persona_id)
    platforms_config = load_platforms_config()
    topic, source_url, source_type = _select_topic(platforms_config, pid)
    return generate_post_for_topic(
        topic=topic,
        source_url=source_url,
        source_type=source_type,
        persona_id=pid,
    )
