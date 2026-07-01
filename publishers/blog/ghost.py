from __future__ import annotations

from publishers.base import Publisher
from shared.models import PostContent, PublishResult


class GhostPublisher(Publisher):
    """
    Stub — enable blog platform in config/platforms.yaml after implementing.

    Ghost Admin API docs:
    https://docs.ghost.org/admin-api/
    """

    def __init__(self, *, platform_config: dict | None = None) -> None:
        self._platform_config = platform_config or {}

    def validate_credentials(self) -> bool:
        return False

    def get_constraints(self) -> dict:
        return {
            "char_limit": 100_000,
            "supports_images": True,
            "supports_links": True,
        }

    def render_preview(self, text: str, profile: dict) -> str:
        return (
            '<div style="font-family:Georgia,serif;max-width:640px;padding:16px;">'
            "<h3>Blog preview</h3>"
            f'<pre style="white-space:pre-wrap">{text[:400]}</pre></div>'
        )

    def publish(self, content: PostContent) -> PublishResult:
        raise NotImplementedError(
            "Ghost blog publisher is not implemented yet. "
            "See CONTRIBUTING.md#adding-a-platform-publisher."
        )
