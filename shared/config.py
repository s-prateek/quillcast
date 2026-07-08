from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _config_dir() -> Path:
    configured = os.environ.get("QUILLCAST_CONFIG_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "config"


def _load_yaml(filename: str) -> dict[str, Any]:
    path = _config_dir() / filename
    if not path.is_file():
        raise RuntimeError(f"Config file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_platforms_config() -> dict[str, Any]:
    return _load_yaml("platforms.yaml")


def load_personas_config() -> dict[str, Any]:
    return _load_yaml("personas.yaml")


def get_default_persona_id() -> str:
    config = load_personas_config()
    return str(config.get("default_persona", "tech")).strip() or "tech"


def get_persona(persona_id: str | None = None) -> dict[str, Any]:
    config = load_personas_config()
    personas = config.get("personas", {})
    pid = (persona_id or get_default_persona_id()).strip()
    persona = personas.get(pid)
    if not isinstance(persona, dict):
        raise RuntimeError(f"Unknown persona: {pid!r}. Check config/personas.yaml")
    return {"id": pid, **persona}


def list_personas() -> list[dict[str, Any]]:
    config = load_personas_config()
    personas = config.get("personas", {})
    return [
        {"id": pid, "label": cfg.get("label", pid)}
        for pid, cfg in personas.items()
        if isinstance(cfg, dict)
    ]


def resolve_author_name(persona: dict[str, Any] | None = None) -> str:
    env_name = os.environ.get("AUTHOR_NAME", "").strip()
    if env_name:
        return env_name
    if persona is None:
        persona = get_persona()
    voice = persona.get("voice", {})
    return str(voice.get("author_name", "Prateek Sharma")).strip() or "Prateek Sharma"


def persona_voice_for_llm(persona: dict[str, Any] | None = None) -> dict[str, Any]:
    """Voice dict for LLM prompts — author_name resolved from env or persona."""
    if persona is None:
        persona = get_persona()
    voice = dict(persona.get("voice", {}))
    voice["author_name"] = resolve_author_name(persona)
    return voice


def rss_feeds_for_persona(persona_id: str | None = None) -> list[dict[str, Any]]:
    persona = get_persona(persona_id)
    platforms = load_platforms_config()
    all_feeds = platforms.get("rss_feeds", {})
    keys = persona.get("rss_feed_keys") or []

    feeds: list[dict[str, Any]] = []
    if isinstance(all_feeds, dict):
        for key in keys:
            feed = all_feeds.get(key)
            if isinstance(feed, dict) and feed.get("url"):
                feeds.append({"key": key, **feed})
        return feeds

    # Legacy list format fallback
    if isinstance(all_feeds, list):
        return list(all_feeds)
    return feeds


def load_topics_config() -> dict[str, Any]:
    """Deprecated shim — returns default persona voice + evergreen topics."""
    persona = get_persona(get_default_persona_id())
    return {
        "voice": persona_voice_for_llm(persona),
        "evergreen_topics": persona.get("evergreen_topics", []),
    }


def enabled_platforms(platforms_config: dict[str, Any]) -> list[str]:
    platforms = platforms_config.get("platforms", {})
    return sorted(name for name, cfg in platforms.items() if cfg.get("enabled"))
