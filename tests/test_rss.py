from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from rss import fetch_articles


def _entry(title: str, link: str, published_at: datetime) -> dict:
    return {
        "title": title,
        "link": link,
        "summary": "Summary",
        "published_parsed": published_at.timetuple()[:6],
    }


@patch("rss.feedparser.parse")
def test_fetch_articles_filters_by_age_and_sorts_newest_first(mock_parse):
    now = datetime.now(timezone.utc)
    mock_parse.return_value.entries = [
        _entry("Older", "https://example.com/old", now - timedelta(hours=12)),
        _entry("Newer", "https://example.com/new", now - timedelta(hours=3)),
        _entry("Too fresh", "https://example.com/fresh", now - timedelta(minutes=30)),
        _entry("Too old", "https://example.com/ancient", now - timedelta(hours=72)),
    ]

    articles = fetch_articles(
        {
            "rss_feeds": [{"url": "https://example.com/feed.xml"}],
            "rss_filter": {
                "min_article_age_hours": 1,
                "max_article_age_hours": 48,
                "max_articles_per_run": 5,
            },
        }
    )

    assert [article.title for article in articles] == ["Newer", "Older"]
