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


def load_topics_config() -> dict[str, Any]:
    return _load_yaml("topics.yaml")


def enabled_platforms(platforms_config: dict[str, Any]) -> list[str]:
    platforms = platforms_config.get("platforms", {})
    return sorted(name for name, cfg in platforms.items() if cfg.get("enabled"))
