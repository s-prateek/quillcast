from __future__ import annotations

from publishers.linkedin import LinkedInPublisher


def render_linkedin_preview(text: str, profile: dict) -> str:
    return LinkedInPublisher().render_preview(text, profile)
