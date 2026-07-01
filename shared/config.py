from __future__ import annotations

import os
<<<<<<< HEAD
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
=======
from typing import Any

import boto3
import yaml


def _s3_client(s3_client=None):
    return s3_client or boto3.client("s3")


def _load_yaml(bucket: str, key: str, *, s3_client=None) -> dict[str, Any]:
    response = _s3_client(s3_client).get_object(Bucket=bucket, Key=key)
    return yaml.safe_load(response["Body"].read().decode("utf-8"))


def _config_bucket(bucket: str | None = None) -> str:
    if bucket:
        return bucket
    name = os.environ.get("CONFIG_BUCKET") or os.environ.get("QUILLCAST_CONFIG_BUCKET")
    if not name:
        raise RuntimeError("CONFIG_BUCKET or QUILLCAST_CONFIG_BUCKET must be set")
    return name


def load_platforms_config(bucket: str | None = None, *, s3_client=None) -> dict[str, Any]:
    return _load_yaml(_config_bucket(bucket), "config/platforms.yaml", s3_client=s3_client)


def load_topics_config(bucket: str | None = None, *, s3_client=None) -> dict[str, Any]:
    return _load_yaml(_config_bucket(bucket), "config/topics.yaml", s3_client=s3_client)
>>>>>>> origin/main


def enabled_platforms(platforms_config: dict[str, Any]) -> list[str]:
    platforms = platforms_config.get("platforms", {})
    return sorted(name for name, cfg in platforms.items() if cfg.get("enabled"))
