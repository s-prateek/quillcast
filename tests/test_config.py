
from shared.config import enabled_platforms


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
