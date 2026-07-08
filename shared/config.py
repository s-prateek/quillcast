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


def _load_yaml_with_fallback(primary: str, fallback: str, *, label: str) -> dict[str, Any]:
    config_dir = _config_dir()
    primary_path = config_dir / primary
    if primary_path.is_file():
        return yaml.safe_load(primary_path.read_text(encoding="utf-8"))

    fallback_path = config_dir / fallback
    if fallback_path.is_file():
        return yaml.safe_load(fallback_path.read_text(encoding="utf-8"))

    raise RuntimeError(
        f"{label} not found. Copy {fallback_path} to {primary_path} "
        f"and customize, or restore {primary_path}."
    )


def load_platforms_config() -> dict[str, Any]:
    """Load platforms.yaml if present, else committed platforms.example.yaml."""
    return _load_yaml_with_fallback(
        "platforms.yaml", "platforms.example.yaml", label="Platform config"
    )


def load_personas_config() -> dict[str, Any]:
    """Load personas.yaml if present, else committed personas.example.yaml."""
    return _load_yaml_with_fallback(
        "personas.yaml", "personas.example.yaml", label="Persona config"
    )


def get_default_persona_id() -> str:
    config = load_personas_config()
    personas = config.get("personas", {})
    if not isinstance(personas, dict) or not personas:
        raise RuntimeError("No personas defined. Add entries under personas: in config/personas.yaml")

    explicit = str(config.get("default_persona", "")).strip()
    if explicit and explicit in personas:
        return explicit

    return next(iter(personas))


def resolve_persona_id(persona_id: str | None = None) -> str:
    """Return a valid persona id, using default when missing or blank."""
    if persona_id and str(persona_id).strip():
        pid = str(persona_id).strip()
        get_persona(pid)
        return pid
    return get_default_persona_id()


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
    return str(voice.get("author_name", "Your Name")).strip() or "Your Name"


def list_rss_categories() -> list[dict[str, str]]:
    """RSS category ids from platforms config (defined or inferred from feeds)."""
    platforms = load_platforms_config()
    defined = platforms.get("rss_categories", {})
    if isinstance(defined, dict) and defined:
        categories: list[dict[str, str]] = []
        for category_id, cfg in defined.items():
            if isinstance(cfg, dict):
                label = str(cfg.get("label", category_id)).strip() or category_id
            else:
                label = str(cfg).strip() or category_id
            categories.append({"id": category_id, "label": label})
        return categories

    all_feeds = platforms.get("rss_feeds", {})
    inferred: set[str] = set()
    if isinstance(all_feeds, dict):
        for feed in all_feeds.values():
            if isinstance(feed, dict):
                category = str(feed.get("category", "")).strip()
                if category:
                    inferred.add(category)
    return [{"id": category_id, "label": category_id} for category_id in sorted(inferred)]


def resolve_ghost_custom_template(
    *,
    persona_id: str | None = None,
    tags: list[str] | None = None,
) -> str | None:
    """Resolve Ghost custom_template from persona, then platform tag/persona maps."""
    pid = str(persona_id or "").strip()
    tag_list = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]

    if pid:
        try:
            persona = get_persona(pid)
            template = (persona.get("blog_defaults") or {}).get("ghost_custom_template")
            if isinstance(template, str) and template.strip():
                return template.strip()
        except RuntimeError:
            pass

    platforms = load_platforms_config()
    blog_cfg = (platforms.get("platforms") or {}).get("blog") or {}
    template_maps = blog_cfg.get("ghost_custom_templates") or {}
    if not isinstance(template_maps, dict):
        return None

    by_persona = template_maps.get("by_persona") or {}
    if pid and isinstance(by_persona, dict):
        persona_template = by_persona.get(pid)
        if isinstance(persona_template, str) and persona_template.strip():
            return persona_template.strip()

    by_tag = template_maps.get("by_tag") or {}
    if isinstance(by_tag, dict):
        tag_lookup = {str(key).strip().lower(): value for key, value in by_tag.items()}
        for tag in tag_list:
            template = tag_lookup.get(tag.lower())
            if isinstance(template, str) and template.strip():
                return template.strip()

    return None


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
    keys = [str(key).strip() for key in (persona.get("rss_feed_keys") or []) if str(key).strip()]
    categories = {
        str(category).strip()
        for category in (persona.get("rss_categories") or [])
        if str(category).strip()
    }

    feeds: list[dict[str, Any]] = []
    if isinstance(all_feeds, dict):
        matched_keys: set[str] = set(keys)
        if categories:
            for key, feed in all_feeds.items():
                if not isinstance(feed, dict):
                    continue
                if str(feed.get("category", "")).strip() in categories:
                    matched_keys.add(str(key))

        for key in sorted(matched_keys):
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
