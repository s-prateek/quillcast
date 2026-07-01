from __future__ import annotations

from publishers.base import Publisher
from shared.models import PostContent, PublishResult


class FacebookPublisher(Publisher):
    """
    Stub — enable in config/platforms.yaml after implementing.

    Facebook Graph API docs:
    https://developers.facebook.com/docs/pages-api/posts
    """

    def __init__(self, *, platform_config: dict | None = None) -> None:
        self._platform_config = platform_config or {}

    def validate_credentials(self) -> bool:
        return False

    def get_constraints(self) -> dict:
        return {
            "char_limit": 500,
            "supports_images": True,
            "supports_links": True,
        }

    def render_preview(self, text: str, profile: dict) -> str:
        name = profile.get("name", "Your Name")
        return (
            f'<div style="font-family:sans-serif;max-width:500px;padding:12px;'
            f'border:1px solid #ddd;border-radius:8px;">'
            f"<strong>{name}</strong><p>{text[:200]}</p></div>"
        )

    def publish(self, content: PostContent) -> PublishResult:
        raise NotImplementedError(
            "Facebook publisher is not implemented yet. "
            "See CONTRIBUTING.md#adding-a-platform-publisher."
        )
