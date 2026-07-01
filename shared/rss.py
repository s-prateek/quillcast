from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    summary: str
    published_at: datetime


def _parse_published(entry: dict[str, Any]) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def _summary_for(entry: dict[str, Any]) -> str:
    return (entry.get("summary") or entry.get("title") or "").strip()


def fetch_articles(platforms_config: dict[str, Any]) -> list[Article]:
    rss_filter = platforms_config.get("rss_filter", {})
    min_age_hours = int(rss_filter.get("min_article_age_hours", 1))
    max_age_hours = int(rss_filter.get("max_article_age_hours", 48))
    max_articles = int(rss_filter.get("max_articles_per_run", 5))

    now = datetime.now(timezone.utc)
    min_published = now - timedelta(hours=max_age_hours)
    max_published = now - timedelta(hours=min_age_hours)

    articles: list[Article] = []
    for feed_cfg in platforms_config.get("rss_feeds", []):
        parsed = feedparser.parse(feed_cfg["url"])
        for entry in parsed.entries:
            published_at = _parse_published(entry)
            if published_at is None:
                continue
            if published_at < min_published or published_at > max_published:
                continue

            link = entry.get("link")
            title = (entry.get("title") or "").strip()
            if not link or not title:
                continue

            articles.append(
                Article(
                    title=title,
                    url=link,
                    summary=_summary_for(entry),
                    published_at=published_at,
                )
            )

    articles.sort(key=lambda article: article.published_at, reverse=True)
    return articles[:max_articles]
