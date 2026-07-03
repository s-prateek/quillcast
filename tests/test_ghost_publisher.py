import json
from unittest.mock import patch

from publishers.blog.ghost import GhostPublisher, make_ghost_jwt
from shared.models import PostContent


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


@patch("publishers.blog.ghost._http_request")
def test_validate_credentials_success(mock_http, tmp_path):
    mock_http.return_value = (200, b'{"site": {"title": "Test"}}')
    token_file = tmp_path / "blog.json"
    token_file.write_text(
        json.dumps({
            "url": "http://localhost:2368",
            "admin_api_key": "id:" + "cd" * 32,
        }),
        encoding="utf-8",
    )
    publisher = GhostPublisher(platform_config={"token_file": str(token_file)})
    assert publisher.validate_credentials() is True


@patch("publishers.blog.ghost._http_request")
def test_publish_creates_draft(mock_http, tmp_path):
    mock_http.return_value = (
        201,
        json.dumps({"posts": [{"uuid": "post-uuid-1", "id": "1"}]}).encode(),
    )
    token_file = tmp_path / "blog.json"
    token_file.write_text(
        json.dumps({
            "url": "http://localhost:2368",
            "admin_api_key": "id:" + "ef" * 32,
        }),
        encoding="utf-8",
    )
    publisher = GhostPublisher(platform_config={"token_file": str(token_file)})
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


@patch("publishers.blog.ghost._http_request")
def test_publish_api_error(mock_http, tmp_path):
    mock_http.return_value = (403, b"Forbidden")
    token_file = tmp_path / "blog.json"
    token_file.write_text(
        json.dumps({
            "url": "http://localhost:2368",
            "admin_api_key": "id:" + "12" * 32,
        }),
        encoding="utf-8",
    )
    publisher = GhostPublisher(platform_config={"token_file": str(token_file)})
    result = publisher.publish(
        PostContent(text="Body", platform="blog", metadata={"title": "T", "status": "draft"})
    )
    assert result.success is False
    assert "403" in (result.error or "")
