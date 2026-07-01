from __future__ import annotations

from abc import ABC, abstractmethod

from shared.models import PostContent, PublishResult


class Publisher(ABC):
    @abstractmethod
    def publish(self, content: PostContent) -> PublishResult:
        """Publish content to the platform."""

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Return True if credentials are present and usable."""

    @abstractmethod
    def get_constraints(self) -> dict:
        """Platform limits, e.g. {"char_limit": 3000}."""

    @abstractmethod
    def render_preview(self, text: str, profile: dict) -> str:
        """Return HTML for local preview (Streamlit injects via components.html)."""
