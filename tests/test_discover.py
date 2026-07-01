from datetime import datetime, timezone
from unittest.mock import patch

from shared.discover import discover_topics
from shared.rss import Article


@patch("shared.discover.curate_topic_candidates")
@patch("shared.discover.fetch_articles")
def test_discover_topics_uses_llm_when_available(mock_fetch, mock_curate):
    mock_fetch.return_value = [
        Article(
            title="AI news",
            url="https://example.com/ai",
            summary="Summary",
            published_at=datetime.now(timezone.utc),
        )
    ]
    from shared.models import TopicCandidate

    mock_curate.return_value = [
        TopicCandidate(
            id="topic-0",
            title="AI news",
            hook="Timely story",
            source_url="https://example.com/ai",
            source_type="rss",
        )
    ]

    topics = discover_topics(use_llm=True)
    assert len(topics) == 1
    assert topics[0].title == "AI news"
    mock_curate.assert_called_once()


@patch("shared.discover.curate_topic_candidates")
@patch("shared.discover.fetch_articles")
def test_discover_topics_falls_back_when_llm_fails(mock_fetch, mock_curate):
    mock_fetch.return_value = [
        Article(
            title="Fallback story",
            url="https://example.com/fallback",
            summary="Plain summary",
            published_at=datetime.now(timezone.utc),
        )
    ]
    mock_curate.side_effect = RuntimeError("LLM unavailable")

    topics = discover_topics(use_llm=True)
    assert topics[0].title == "Fallback story"
    assert topics[0].source_type == "rss"
