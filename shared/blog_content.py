from __future__ import annotations

import json
from typing import Any


class BlogContentError(ValueError):
    """Raised when blog JSON is missing required fields."""


def parse_blog_content(raw: str) -> dict[str, Any]:
    """Parse blog payload from JSON string. Returns {title, body, tags}."""
    stripped = raw.strip()
    if not stripped:
        raise BlogContentError("Blog content is empty")

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise BlogContentError(f"Blog content must be valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise BlogContentError("Blog content must be a JSON object")

    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()
    tags_raw = data.get("tags", [])

    if not title:
        raise BlogContentError("Blog content missing 'title'")
    if not body:
        raise BlogContentError("Blog content missing 'body'")

    tags: list[str] = []
    if isinstance(tags_raw, list):
        tags = [str(tag).strip() for tag in tags_raw if str(tag).strip()]
    elif isinstance(tags_raw, str) and tags_raw.strip():
        tags = [part.strip() for part in tags_raw.split(",") if part.strip()]

    return {"title": title, "body": body, "tags": tags}


def serialize_blog_content(*, title: str, body: str, tags: list[str]) -> str:
    """Serialize blog fields to JSON for draft storage."""
    return json.dumps(
        {
            "title": title.strip(),
            "body": body.strip(),
            "tags": [tag.strip() for tag in tags if tag.strip()],
        },
        indent=2,
    )


def blog_content_from_variant(variant: Any) -> dict[str, Any] | None:
    """Extract blog fields from a ContentVariants entry (dict or JSON string)."""
    if isinstance(variant, dict):
        try:
            return parse_blog_content(json.dumps(variant))
        except BlogContentError:
            return None
    if isinstance(variant, str) and variant.strip():
        try:
            return parse_blog_content(variant)
        except BlogContentError:
            return None
    return None
