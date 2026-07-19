import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.config import (
    default_platforms_for_persona,
    enabled_platforms,
    load_platforms_config,
    persona_platforms,
)
from shared.drafts import delete_record, get_record, put_record
from shared.generate import generate_post_for_topic, generate_platform_content
from shared.models import PostRecord, TargetRecord


def test_enabled_platforms_returns_only_enabled_sorted():
    config = {
        "platforms": {
            "blog": {"enabled": False},
            "linkedin": {"enabled": True},
            "facebook": {"enabled": False},
        }
    }

    assert enabled_platforms(config) == ["linkedin"]


def test_enabled_platforms_empty_when_none_enabled():
    config = {"platforms": {"linkedin": {"enabled": False}}}

    assert enabled_platforms(config) == []


def test_load_platforms_falls_back_to_example(monkeypatch, tmp_path):
    repo_config = Path(__file__).resolve().parent.parent / "config"
    shutil.copy(repo_config / "platforms.example.yaml", tmp_path / "platforms.example.yaml")
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))
    config = load_platforms_config()
    assert config["platforms"]["linkedin"]["enabled"] is False
    assert "example" in config["rss_feeds"]


def test_persona_platforms_uses_persona_subset(monkeypatch, tmp_path):
    (tmp_path / "platforms.example.yaml").write_text(
        """
platforms:
  linkedin:
    enabled: true
  blog:
    enabled: true
  facebook:
    enabled: true
rss_feeds: {}
rss_filter:
  max_articles_per_run: 5
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "personas.example.yaml").write_text(
        """
default_persona: tech
personas:
  tech:
    label: Tech
    platforms:
      - linkedin
      - blog
    default_platforms:
      - linkedin
    voice:
      author_name: Test
      description: Voice
      target_audience: Engineers
    rss_feed_keys: []
    evergreen_topics:
      - Topic
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))

    assert persona_platforms("tech") == ["blog", "linkedin"]
    assert default_platforms_for_persona("tech") == ["linkedin"]


def test_default_platforms_falls_back_to_all_persona_platforms(monkeypatch, tmp_path):
    (tmp_path / "platforms.example.yaml").write_text(
        """
platforms:
  linkedin:
    enabled: true
  blog:
    enabled: true
rss_feeds: {}
rss_filter:
  max_articles_per_run: 5
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "personas.example.yaml").write_text(
        """
default_persona: writer
personas:
  writer:
    label: Writer
    voice:
      author_name: Test
      description: Voice
      target_audience: Readers
    rss_feed_keys: []
    evergreen_topics:
      - Topic
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))

    assert default_platforms_for_persona("writer") == ["blog", "linkedin"]


@patch("shared.generate.generate_content_variants")
def test_generate_post_for_topic_uses_default_platforms_only(mock_variants, monkeypatch, tmp_path):
    mock_variants.return_value = {"linkedin": "LinkedIn post text"}

    (tmp_path / "platforms.example.yaml").write_text(
        """
platforms:
  linkedin:
    enabled: true
  blog:
    enabled: true
rss_feeds: {}
rss_filter:
  max_articles_per_run: 5
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "personas.example.yaml").write_text(
        """
default_persona: tech
personas:
  tech:
    label: Tech
    default_platforms:
      - linkedin
    voice:
      author_name: Test
      description: Voice
      target_audience: Engineers
    rss_feed_keys: []
    evergreen_topics:
      - Topic
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("QUILLCAST_DRAFTS_DIR", str(tmp_path / "drafts"))

    result = generate_post_for_topic(topic="Test topic", persona_id="tech")

    mock_variants.assert_called_once()
    assert mock_variants.call_args.kwargs["enabled_platforms"] == ["linkedin"]
    assert result["platforms"] == ["linkedin"]

    record = get_record(result["post_id"])
    assert record is not None
    assert set(record.Targets.keys()) == {"blog", "linkedin"}
    assert "blog" not in record.ContentVariants


@patch("shared.generate.generate_content_variants")
def test_generate_platform_content_adds_single_platform(mock_variants, monkeypatch, tmp_path):
    mock_variants.return_value = {"blog": {"title": "T", "body": "B", "tags": []}}

    (tmp_path / "platforms.example.yaml").write_text(
        """
platforms:
  linkedin:
    enabled: true
  blog:
    enabled: true
rss_feeds: {}
rss_filter:
  max_articles_per_run: 5
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "personas.example.yaml").write_text(
        """
default_persona: tech
personas:
  tech:
    label: Tech
    default_platforms:
      - linkedin
    voice:
      author_name: Test
      description: Voice
      target_audience: Engineers
    rss_feed_keys: []
    evergreen_topics:
      - Topic
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))
    drafts_dir = tmp_path / "drafts"
    monkeypatch.setenv("QUILLCAST_DRAFTS_DIR", str(drafts_dir))

    created = generate_post_for_topic(topic="Test topic", persona_id="tech")
    generate_platform_content(post_id=created["post_id"], platform="blog")

    record = get_record(created["post_id"])
    assert record is not None
    assert "blog" in record.ContentVariants
    assert mock_variants.call_args_list[-1].kwargs["enabled_platforms"] == ["blog"]


def test_delete_record_removes_draft_file(monkeypatch, tmp_path):
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    monkeypatch.setenv("QUILLCAST_DRAFTS_DIR", str(drafts_dir))

    record = PostRecord(
        PostID="draft-1",
        CreatedAt="2026-01-01T00:00:00Z",
        UpdatedAt="2026-01-01T00:00:00Z",
        Topic="Topic",
        SourceURL="",
        SourceType="custom",
        OverallStatus="PENDING",
        ContentVariants={"linkedin": "text"},
        Targets={"linkedin": TargetRecord()},
    )
    put_record(record)
    assert get_record("draft-1") is not None

    assert delete_record("draft-1") is True
    assert get_record("draft-1") is None
    assert delete_record("draft-1") is False
