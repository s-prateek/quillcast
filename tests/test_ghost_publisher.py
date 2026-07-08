import json
import os
from unittest.mock import patch

from publishers.blog.ghost import GhostPublisher, make_ghost_jwt
from shared.models import PostContent

GHOST_ENV = {
    "GHOST_URL": "http://localhost:2368",
    "GHOST_ADMIN_API_KEY": "id:" + "cd" * 32,
}


def test_make_ghost_jwt_has_three_segments():
    # Secret must be hex (Ghost Admin API format)
    token = make_ghost_jwt(
        "abc123:" + "ab" * 32,
        now=1_700_000_000,
    )
    parts = token.split(".")
    assert len(parts) == 3
    assert parts[0]
    assert parts[1]
    assert parts[2]


@patch.dict(os.environ, GHOST_ENV, clear=False)
@patch("publishers.blog.ghost._http_request")
def test_validate_credentials_success(mock_http):
    mock_http.return_value = (200, b'{"site": {"title": "Test"}}')
    publisher = GhostPublisher()
    assert publisher.validate_credentials() is True


@patch.dict(os.environ, GHOST_ENV, clear=False)
@patch("publishers.blog.ghost._http_request")
def test_publish_creates_draft(mock_http):
    mock_http.return_value = (
        201,
        json.dumps({"posts": [{"uuid": "post-uuid-1", "id": "1"}]}).encode(),
    )
    publisher = GhostPublisher()
    result = publisher.publish(
        PostContent(
            text="## Hello\n\nWorld",
            platform="blog",
            metadata={"title": "Test Post", "tags": ["AI"], "status": "draft"},
        )
    )
    assert result.success is True
    assert result.platform_post_id == "post-uuid-1"

    call_args = mock_http.call_args
    body = json.loads(call_args.kwargs["body"].decode())
    post = body["posts"][0]
    assert post["title"] == "Test Post"
    assert post["status"] == "draft"
    assert post["tags"] == [{"name": "AI"}]
    assert "<h2>Hello</h2>" in post["html"]
    assert "custom_template" not in post


@patch.dict(os.environ, GHOST_ENV, clear=False)
@patch("publishers.blog.ghost._http_request")
def test_publish_games_tag_sets_custom_template(mock_http):
    mock_http.return_value = (
        201,
        json.dumps({"posts": [{"uuid": "post-uuid-2", "id": "2"}]}).encode(),
    )
    publisher = GhostPublisher()
    result = publisher.publish(
        PostContent(
            text="Body",
            platform="blog",
            metadata={"title": "Switch picks", "tags": ["Games", "Nintendo"], "status": "draft"},
        )
    )
    assert result.success is True
    body = json.loads(mock_http.call_args.kwargs["body"].decode())
    assert body["posts"][0]["custom_template"] == "custom-games"


@patch.dict(os.environ, GHOST_ENV, clear=False)
@patch("publishers.blog.ghost._http_request")
def test_publish_gaming_persona_sets_custom_template(mock_http):
    mock_http.return_value = (
        201,
        json.dumps({"posts": [{"uuid": "post-uuid-3", "id": "3"}]}).encode(),
    )
    publisher = GhostPublisher()
    result = publisher.publish(
        PostContent(
            text="Body",
            platform="blog",
            metadata={
                "title": "Nintendo take",
                "tags": ["Nintendo"],
                "status": "draft",
                "persona_id": "gaming",
            },
        )
    )
    assert result.success is True
    body = json.loads(mock_http.call_args.kwargs["body"].decode())
    assert body["posts"][0]["custom_template"] == "custom-games"

@patch.dict(os.environ, GHOST_ENV, clear=False)
@patch("publishers.blog.ghost._http_request")
def test_publish_api_error(mock_http):
    mock_http.return_value = (403, b"Forbidden")
    publisher = GhostPublisher()
    result = publisher.publish(
        PostContent(text="Body", platform="blog", metadata={"title": "T", "status": "draft"})
    )
    assert result.success is False
    assert "403" in (result.error or "")
