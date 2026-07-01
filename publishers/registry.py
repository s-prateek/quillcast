from __future__ import annotations

from typing import Any

from publishers.base import Publisher
from publishers.linkedin import LinkedInPublisher

_REGISTRY: dict[str, type[Publisher]] = {
    "linkedin": LinkedInPublisher,
}


def get(platform: str, *, platform_config: dict[str, Any] | None = None) -> Publisher:
    cls = _REGISTRY.get(platform)
    if cls is None:
        raise ValueError(f"No publisher registered for platform: {platform!r}")
    return cls(platform_config=platform_config or {})
