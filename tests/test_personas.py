from pathlib import Path
import shutil

import pytest

from shared.config import (
    get_default_persona_id,
    get_persona,
    list_personas,
    list_rss_categories,
    load_personas_config,
    persona_voice_for_llm,
    resolve_ghost_custom_template,
    resolve_persona_id,
    rss_feeds_for_persona,
)


@pytest.fixture
def example_config_dir(tmp_path, monkeypatch):
    repo_config = Path(__file__).resolve().parent.parent / "config"
    shutil.copy(repo_config / "personas.example.yaml", tmp_path / "personas.example.yaml")
    shutil.copy(repo_config / "platforms.example.yaml", tmp_path / "platforms.example.yaml")
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_list_personas_returns_configured_ids(example_config_dir):
    ids = {p["id"] for p in list_personas()}
    assert "default" in ids


def test_get_persona_default_has_voice_and_feed_keys(example_config_dir):
    persona = get_persona("default")
    assert persona.get("voice", {}).get("description")
    assert "example" in persona.get("rss_feed_keys", [])


def test_rss_feeds_for_persona_returns_urls(example_config_dir):
    feeds = rss_feeds_for_persona("default")
    assert len(feeds) == 1
    assert feeds[0]["url"] == "https://example.com/feed.xml"


def test_rss_feeds_for_persona_by_category(monkeypatch, tmp_path):
    (tmp_path / "platforms.example.yaml").write_text(
        """
rss_categories:
  news:
    label: News
platforms:
  linkedin:
    enabled: false
rss_feeds:
  feed_a:
    url: https://example.com/rss
    category: news
rss_filter:
  min_article_age_hours: 1
  max_article_age_hours: 48
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
    rss_categories:
      - news
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))
    feeds = rss_feeds_for_persona("writer")
    assert len(feeds) == 1
    assert feeds[0]["key"] == "feed_a"


def test_list_rss_categories_from_platforms(example_config_dir):
    categories = {item["id"] for item in list_rss_categories()}
    assert "general" in categories


def test_resolve_ghost_custom_template_from_persona(monkeypatch, tmp_path):
    (tmp_path / "platforms.example.yaml").write_text(
        """
platforms:
  blog:
    enabled: false
    ghost_custom_templates:
      by_tag: {}
      by_persona: {}
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "personas.example.yaml").write_text(
        """
default_persona: games
personas:
  games:
    label: Games
    voice:
      author_name: Test
      description: Voice
      target_audience: Gamers
    blog_defaults:
      ghost_custom_template: custom-games
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))
    template = resolve_ghost_custom_template(persona_id="games", tags=["Nintendo"])
    assert template == "custom-games"


def test_resolve_persona_id_uses_default_for_blank(example_config_dir):
    assert resolve_persona_id("") == get_default_persona_id()
    assert resolve_persona_id(None) == get_default_persona_id()


def test_resolve_persona_id_rejects_unknown(example_config_dir):
    with pytest.raises(RuntimeError, match="Unknown persona"):
        resolve_persona_id("not-a-real-persona")


def test_persona_voice_uses_env_author_name(example_config_dir, monkeypatch):
    monkeypatch.setenv("AUTHOR_NAME", "Env Author")
    voice = persona_voice_for_llm(get_persona("default"))
    assert voice["author_name"] == "Env Author"


def test_persona_voice_falls_back_to_yaml(example_config_dir, monkeypatch):
    monkeypatch.delenv("AUTHOR_NAME", raising=False)
    persona = get_persona("default")
    voice = persona_voice_for_llm(persona)
    assert voice["author_name"] == persona["voice"]["author_name"]


def test_load_personas_falls_back_to_example(example_config_dir):
    config = load_personas_config()
    assert "default" in config.get("personas", {})
    voice = persona_voice_for_llm(get_persona("default"))
    assert voice["author_name"] == "Your Name"


def test_default_persona_matches_config(example_config_dir):
    assert get_default_persona_id() == "default"
