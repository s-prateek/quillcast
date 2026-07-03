import json

import pytest

from shared.blog_content import BlogContentError, parse_blog_content, serialize_blog_content
from shared.publish import build_post_content


def test_parse_blog_content_valid():
    raw = json.dumps({
        "title": "Hello Ghost",
        "body": "## Intro\n\nParagraph.",
        "tags": ["AI", "Tools"],
    })
    parsed = parse_blog_content(raw)
    assert parsed["title"] == "Hello Ghost"
    assert "Intro" in parsed["body"]
    assert parsed["tags"] == ["AI", "Tools"]


def test_parse_blog_content_tags_from_string():
    raw = json.dumps({"title": "T", "body": "B", "tags": "AI, Tools"})
    parsed = parse_blog_content(raw)
    assert parsed["tags"] == ["AI", "Tools"]


def test_parse_blog_content_missing_title():
    with pytest.raises(BlogContentError, match="title"):
        parse_blog_content(json.dumps({"body": "only body"}))


def test_serialize_blog_content_roundtrip():
    raw = serialize_blog_content(title="Title", body="Body", tags=["AI"])
    parsed = parse_blog_content(raw)
    assert parsed == {"title": "Title", "body": "Body", "tags": ["AI"]}


def test_build_post_content_blog():
    raw = serialize_blog_content(title="Title", body="Body", tags=["AI"])
    content = build_post_content(
        platform="blog",
        body=raw,
        platform_config={"default_status": "draft"},
    )
    assert content.text == "Body"
    assert content.metadata["title"] == "Title"
    assert content.metadata["tags"] == ["AI"]
    assert content.metadata["status"] == "draft"


def test_build_post_content_linkedin_unchanged():
    content = build_post_content(platform="linkedin", body="Hello", platform_config={})
    assert content.text == "Hello"
    assert content.metadata == {}
