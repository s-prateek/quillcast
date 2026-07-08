from __future__ import annotations

import base64
import html
import json
import os
import time
import urllib.error
import urllib.request
from hashlib import sha256
from hmac import HMAC
from typing import Any

import markdown

from publishers.base import Publisher
from shared.blog_content import BlogContentError, parse_blog_content
from shared.models import PostContent, PublishResult

JWT_TTL_SECONDS = 300


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def _load_config() -> dict[str, str]:
    url = os.environ.get("GHOST_URL", "").strip()
    admin_api_key = os.environ.get("GHOST_ADMIN_API_KEY", "").strip()

    if not url:
        raise RuntimeError(
            "Ghost URL not configured. Set GHOST_URL in .env (see .env.example)."
        )
    if not admin_api_key or ":" not in admin_api_key:
        raise RuntimeError(
            "Ghost Admin API key not configured. Set GHOST_ADMIN_API_KEY in .env "
            "(see .env.example)."
        )

    return {"url": _normalize_url(url), "admin_api_key": admin_api_key}


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _secret_bytes(secret: str) -> bytes:
    """Ghost Admin API secrets are hex-encoded; decode before HMAC."""
    return bytes.fromhex(secret)


def make_ghost_jwt(admin_api_key: str, *, now: int | None = None) -> str:
    """Build a Ghost Admin API JWT (HS256)."""
    key_id, secret = admin_api_key.split(":", 1)
    issued_at = int(time.time() if now is None else now)
    header = {"alg": "HS256", "typ": "JWT", "kid": key_id}
    payload = {
        "iat": issued_at,
        "exp": issued_at + JWT_TTL_SECONDS,
        "aud": "/admin/",
    }

    header_segment = _base64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_segment = _base64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = HMAC(_secret_bytes(secret), signing_input, sha256).digest()
    signature_segment = _base64url_encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _http_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None = None,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _markdown_to_html(body: str) -> str:
    return markdown.markdown(
        body,
        extensions=["fenced_code", "tables", "nl2br"],
    )


def _ghost_tags(tags: list[str]) -> list[dict[str, str]]:
    return [{"name": tag} for tag in tags if tag.strip()]


def _resolve_custom_template(metadata: dict[str, Any], tags: list[str]) -> str | None:
    explicit = metadata.get("ghost_custom_template")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    return None


def ghost_admin_edit_url(site_url: str, post_uuid: str) -> str:
    return f"{_normalize_url(site_url)}/ghost/#/editor/post/{post_uuid}"


class GhostPublisher(Publisher):
    """
    Publish blog posts to Ghost via the Admin API.

    Docs: https://docs.ghost.org/admin-api/
    """

    def __init__(self, *, platform_config: dict | None = None) -> None:
        self._platform_config = platform_config or {}

    def _config(self) -> dict[str, str]:
        return _load_config()

    def _api_request(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = self._config()
        jwt = make_ghost_jwt(config["admin_api_key"])
        url = f"{config['url']}{path}"
        headers = {
            "Authorization": f"Ghost {jwt}",
            "Accept-Version": "v5.0",
        }
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")

        status, raw = _http_request(method=method, url=url, headers=headers, body=body)
        text = raw.decode("utf-8", errors="replace")
        if status not in {200, 201}:
            raise RuntimeError(f"Ghost API {method} {path} failed ({status}): {text}")

        if not text.strip():
            return {}
        return json.loads(text)

    def validate_credentials(self) -> bool:
        try:
            self._api_request(method="GET", path="/ghost/api/admin/site/")
            return True
        except (OSError, RuntimeError, json.JSONDecodeError, ValueError):
            return False

    def get_constraints(self) -> dict:
        return {
            "char_limit": 100_000,
            "supports_images": False,
            "supports_links": True,
        }

    def _parse_for_preview(self, text: str) -> dict[str, Any]:
        try:
            return parse_blog_content(text)
        except BlogContentError:
            return {"title": "Blog post", "body": text, "tags": []}

    def render_preview(self, text: str, profile: dict) -> str:
        parsed = self._parse_for_preview(text)
        title = html.escape(parsed["title"])
        body_html = _markdown_to_html(parsed["body"])
        tags = parsed.get("tags") or []
        tag_html = " ".join(
            f'<span style="background:#f1f5f9;color:#0f172a;padding:2px 8px;border-radius:4px;'
            f'font-size:12px;font-family:monospace;">#{html.escape(tag)}</span>'
            for tag in tags
        )
        site_name = html.escape(profile.get("site_name", profile.get("name", "Your Blog")))
        return f"""
        <div style="font-family:Georgia,'Source Serif 4',serif;max-width:720px;
            border:1px solid #e2e8f0;border-radius:8px;padding:24px;background:#fff;">
          <div style="font-family:sans-serif;font-size:12px;color:#64748b;margin-bottom:12px;">
            {site_name} · blog preview
          </div>
          <h2 style="font-family:sans-serif;font-size:28px;margin:0 0 16px;color:#0f172a;">{title}</h2>
          <div style="margin-bottom:16px;">{tag_html}</div>
          <div style="font-size:17px;line-height:1.7;color:#334155;">{body_html}</div>
        </div>
        """

    def publish(self, content: PostContent) -> PublishResult:
        metadata = dict(content.metadata or {})
        title = str(metadata.get("title", "")).strip()
        tags = metadata.get("tags") or []
        status = str(metadata.get("status", "draft")).strip() or "draft"
        body = content.text.strip()

        if not title:
            try:
                parsed = parse_blog_content(body)
            except BlogContentError as exc:
                return PublishResult(success=False, error=str(exc))
            title = parsed["title"]
            body = parsed["body"]
            tags = parsed["tags"] or tags
        elif not body:
            return PublishResult(success=False, error="Blog post body is empty")

        if not title:
            return PublishResult(success=False, error="Blog post title is empty")
        if status not in {"draft", "published", "scheduled"}:
            return PublishResult(success=False, error=f"Invalid Ghost post status: {status!r}")

        tag_list = tags if isinstance(tags, list) else []
        custom_template = _resolve_custom_template(metadata, tag_list)

        constraints = self.get_constraints()
        char_limit = int(constraints["char_limit"])
        if len(body) > char_limit:
            return PublishResult(
                success=False,
                error=f"Post body exceeds limit ({len(body)}/{char_limit} chars)",
            )

        try:
            html_body = _markdown_to_html(body)
            post_payload: dict[str, Any] = {
                "title": title,
                "html": html_body,
                "status": status,
                "tags": _ghost_tags(tag_list),
            }
            if custom_template:
                post_payload["custom_template"] = custom_template
            response = self._api_request(
                method="POST",
                path="/ghost/api/admin/posts/?source=html",
                payload={"posts": [post_payload]},
            )
            posts = response.get("posts") or []
            if not posts:
                return PublishResult(success=False, error="Ghost API returned no post")

            post = posts[0]
            post_uuid = str(post.get("uuid") or post.get("id") or "")
            if not post_uuid:
                return PublishResult(success=False, error="Ghost API response missing post id")

            return PublishResult(success=True, platform_post_id=post_uuid)
        except Exception as exc:  # noqa: BLE001 — surface API errors to caller
            return PublishResult(success=False, error=str(exc))
