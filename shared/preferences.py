from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from shared.config import get_default_persona_id


def _preferences_path() -> Path:
    configured = os.environ.get("QUILLCAST_PREFERENCES_FILE", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "data" / "preferences.json"


def load_preferences() -> dict[str, Any]:
    path = _preferences_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_preferences(preferences: dict[str, Any]) -> None:
    path = _preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preferences, indent=2), encoding="utf-8")


def get_active_persona_id() -> str:
    prefs = load_preferences()
    persona_id = str(prefs.get("active_persona_id", "")).strip()
    if persona_id:
        return persona_id
    return get_default_persona_id()


def set_active_persona_id(persona_id: str) -> None:
    prefs = load_preferences()
    prefs["active_persona_id"] = persona_id
    save_preferences(prefs)


def get_selected_model_id(provider: str | None = None) -> str:
    from shared.config import get_llm_provider

    pid = provider or get_llm_provider()
    prefs = load_preferences()
    models = prefs.get("llm_model_by_provider", {})
    if isinstance(models, dict):
        selected = str(models.get(pid, "")).strip()
        if selected:
            return selected
    return ""


def set_selected_model_id(model_id: str, *, provider: str | None = None) -> None:
    from shared.config import get_llm_provider

    pid = provider or get_llm_provider()
    prefs = load_preferences()
    models = prefs.get("llm_model_by_provider", {})
    if not isinstance(models, dict):
        models = {}
    models[pid] = model_id.strip()
    prefs["llm_model_by_provider"] = models
    save_preferences(prefs)
