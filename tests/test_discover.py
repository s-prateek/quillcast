import shutil
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from shared.discover import discover_topics
from shared.rss import Article


@patch("shared.discover.curate_topic_candidates")
@patch("shared.discover.fetch_articles")
def test_discover_topics_uses_llm_when_available(mock_fetch, mock_curate, monkeypatch, tmp_path):
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

    repo_config = Path(__file__).resolve().parent.parent / "config"
    shutil.copy(repo_config / "personas.example.yaml", tmp_path / "personas.example.yaml")
    shutil.copy(repo_config / "platforms.example.yaml", tmp_path / "platforms.example.yaml")
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))

    topics = discover_topics(persona_id="default", use_llm=True)
    assert len(topics) == 1
    assert topics[0].title == "AI news"
    mock_curate.assert_called_once()


@patch("shared.discover.curate_topic_candidates")
@patch("shared.discover.fetch_articles")
def test_discover_topics_passes_exclude_titles(mock_fetch, mock_curate, monkeypatch, tmp_path):
    mock_fetch.return_value = [
        Article(
            title="Fresh story",
            url="https://example.com/fresh",
            summary="Summary",
            published_at=datetime.now(timezone.utc),
        )
    ]
    mock_curate.return_value = []

    repo_config = Path(__file__).resolve().parent.parent / "config"
    shutil.copy(repo_config / "personas.example.yaml", tmp_path / "personas.example.yaml")
    shutil.copy(repo_config / "platforms.example.yaml", tmp_path / "platforms.example.yaml")
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))

    discover_topics(persona_id="default", use_llm=True, exclude_titles=["Already shown"])
    mock_curate.assert_called_once()
    assert mock_curate.call_args.kwargs["exclude_titles"] == ["Already shown"]


@patch("shared.discover.curate_topic_candidates")
@patch("shared.discover.fetch_articles")
def test_discover_topics_falls_back_when_llm_fails(mock_fetch, mock_curate, monkeypatch, tmp_path):
    mock_fetch.return_value = [
        Article(
            title="Fallback story",
            url="https://example.com/fallback",
            summary="Plain summary",
            published_at=datetime.now(timezone.utc),
        )
    ]
    mock_curate.side_effect = RuntimeError("LLM unavailable")

    repo_config = Path(__file__).resolve().parent.parent / "config"
    shutil.copy(repo_config / "personas.example.yaml", tmp_path / "personas.example.yaml")
    shutil.copy(repo_config / "platforms.example.yaml", tmp_path / "platforms.example.yaml")
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))

    topics = discover_topics(persona_id="default", use_llm=True)
    assert topics[0].title == "Fallback story"
    assert topics[0].source_type == "rss"
