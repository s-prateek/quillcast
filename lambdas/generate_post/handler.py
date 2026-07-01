from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from bedrock import generate_content_variants
from rss import fetch_articles

from shared.config import enabled_platforms, load_platforms_config, load_topics_config
from shared.dynamodb import draft_targets_for_platforms, put_record
from shared.models import PostRecord

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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


def generate_post(*, config_bucket: str | None = None, table_name: str | None = None) -> dict[str, Any]:
    bucket = config_bucket or os.environ.get("CONFIG_BUCKET") or os.environ.get("QUILLCAST_CONFIG_BUCKET")
    drafts_table = table_name or os.environ.get("DRAFTS_TABLE_NAME", "quillcast-drafts")
    if not bucket:
        raise RuntimeError("CONFIG_BUCKET or QUILLCAST_CONFIG_BUCKET must be set")

    platforms_config = load_platforms_config(bucket)
    topics_config = load_topics_config(bucket)
    platforms = enabled_platforms(platforms_config)
    if not platforms:
        raise RuntimeError("No platforms are enabled in config/platforms.yaml")

    topic, source_url, source_type = _select_topic(platforms_config, topics_config)
    voice = topics_config.get("voice", {})
    content_variants = generate_content_variants(
        topic=topic,
        source_url=source_url or "evergreen",
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
    put_record(drafts_table, record)

    logger.info("Created draft %s for topic %r", record.PostID, record.Topic)
    return {
        "post_id": record.PostID,
        "topic": record.Topic,
        "source_type": record.SourceType,
        "platforms": platforms,
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    result = generate_post()
    return {"statusCode": 200, "body": result}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(generate_post())
