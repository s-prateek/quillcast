import shutil
from pathlib import Path

from shared.config import enabled_platforms, load_platforms_config


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
