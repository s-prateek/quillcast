from shared.config import (
    get_default_persona_id,
    get_persona,
    list_personas,
    persona_voice_for_llm,
    rss_feeds_for_persona,
)


def test_list_personas_includes_tech_and_gaming():
    ids = {p["id"] for p in list_personas()}
    assert "tech" in ids
    assert "gaming" in ids


def test_get_persona_tech_has_feed_keys():
    persona = get_persona("tech")
    assert "hn" in persona.get("rss_feed_keys", [])
    assert persona.get("blog_defaults", {}).get("tags")


def test_get_persona_gaming_has_nintendo_and_ps_feeds():
    persona = get_persona("gaming")
    keys = persona.get("rss_feed_keys", [])
    assert "nintendo_life" in keys
    assert "push_square" in keys
    assert "ign" in keys
    assert "level design" not in persona.get("voice", {}).get("description", "").lower()


def test_rss_feeds_for_persona_returns_urls():
    feeds = rss_feeds_for_persona("gaming")
    assert len(feeds) >= 5
    assert all(feed.get("url") for feed in feeds)


def test_persona_voice_uses_env_author_name(monkeypatch):
    monkeypatch.setenv("AUTHOR_NAME", "Env Author")
    voice = persona_voice_for_llm(get_persona("tech"))
    assert voice["author_name"] == "Env Author"


def test_persona_voice_falls_back_to_yaml(monkeypatch):
    monkeypatch.delenv("AUTHOR_NAME", raising=False)
    voice = persona_voice_for_llm(get_persona("tech"))
    assert voice["author_name"] == "Prateek Sharma"


def test_default_persona_is_tech():
    assert get_default_persona_id() == "tech"
