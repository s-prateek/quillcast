from __future__ import annotations

import html
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from publishers.base import Publisher
from shared.models import PostContent, PublishResult

LINKEDIN_API_BASE = "https://api.linkedin.com"
DEFAULT_LINKEDIN_VERSION = "202507"
REFRESH_WINDOW_DAYS = 7
MAX_RETRIES = 3
RETRY_BASE_SECONDS = 2


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _token_path(platform_config: dict) -> Path:
    configured = platform_config.get("token_file", "data/tokens/linkedin.json")
    path = Path(configured)
    if not path.is_absolute():
        path = _project_root() / path
    return path


def _linkedin_version() -> str:
    return os.environ.get("LINKEDIN_VERSION", DEFAULT_LINKEDIN_VERSION).strip()


def _load_tokens(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"LinkedIn token file not found: {path}. Run scripts/linkedin_oauth.py")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_tokens(path: Path, tokens: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")


def _parse_expiry(token_expiry: str) -> datetime:
    normalized = token_expiry.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _http_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def _refresh_access_token(tokens: dict, token_path: Path) -> dict:
    client_id = os.environ.get("LINKEDIN_CLIENT_ID", "").strip()
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "").strip()
    refresh_token = tokens.get("refresh_token", "").strip()

    if not client_id or not client_secret:
        raise RuntimeError("LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET required to refresh tokens")
    if not refresh_token:
        raise RuntimeError("No refresh_token in token file. Re-run scripts/linkedin_oauth.py")

    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    status, _, raw = _http_request(
        method="POST",
        url="https://www.linkedin.com/oauth/v2/accessToken",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=payload,
    )
    if status != 200:
        raise RuntimeError(f"Token refresh failed ({status}): {raw.decode('utf-8', errors='replace')}")

    response = json.loads(raw.decode("utf-8"))
    expires_in = int(response.get("expires_in", 5184000))
    tokens["access_token"] = response["access_token"]
    if response.get("refresh_token"):
        tokens["refresh_token"] = response["refresh_token"]
    tokens["token_expiry"] = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()
    _save_tokens(token_path, tokens)
    return tokens


def _ensure_fresh_tokens(tokens: dict, token_path: Path) -> dict:
    expiry_raw = tokens.get("token_expiry")
    if not expiry_raw:
        return tokens

    expiry = _parse_expiry(expiry_raw)
    if expiry - datetime.now(timezone.utc) > timedelta(days=REFRESH_WINDOW_DAYS):
        return tokens

    return _refresh_access_token(tokens, token_path)


def _fetch_author_urn(access_token: str) -> str:
    status, _, raw = _http_request(
        method="GET",
        url=f"{LINKEDIN_API_BASE}/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if status != 200:
        raise RuntimeError(f"Failed to fetch LinkedIn userinfo ({status}): {raw.decode('utf-8', errors='replace')}")

    profile = json.loads(raw.decode("utf-8"))
    member_id = profile.get("sub")
    if not member_id:
        raise RuntimeError("LinkedIn userinfo response missing 'sub' field")
    return f"urn:li:person:{member_id}"


def _author_urn(tokens: dict, token_path: Path) -> str:
    cached = tokens.get("author_urn")
    if cached:
        return cached

    author_urn = _fetch_author_urn(tokens["access_token"])
    tokens["author_urn"] = author_urn
    _save_tokens(token_path, tokens)
    return author_urn


def _create_post(*, access_token: str, author_urn: str, text: str) -> str:
    body = json.dumps({
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": _linkedin_version(),
    }

    last_error = ""
    for attempt in range(MAX_RETRIES):
        status, response_headers, raw = _http_request(
            method="POST",
            url=f"{LINKEDIN_API_BASE}/rest/posts",
            headers=headers,
            body=body,
        )
        if status in {200, 201}:
            post_id = response_headers.get("x-restli-id") or response_headers.get("X-Restli-Id")
            if post_id:
                return post_id
            if raw:
                payload = json.loads(raw.decode("utf-8"))
                if isinstance(payload, dict) and payload.get("id"):
                    return str(payload["id"])
            return "unknown"

        last_error = raw.decode("utf-8", errors="replace")
        if status == 429 and attempt < MAX_RETRIES - 1:
            delay = RETRY_BASE_SECONDS * (2**attempt) + random.uniform(0, 1)
            time.sleep(delay)
            continue
        raise RuntimeError(f"LinkedIn post failed ({status}): {last_error}")

    raise RuntimeError(f"LinkedIn post failed after retries: {last_error}")


class LinkedInPublisher(Publisher):
    def __init__(self, *, platform_config: dict | None = None) -> None:
        self._platform_config = platform_config or {}

    def _token_file(self) -> Path:
        return _token_path(self._platform_config)

    def validate_credentials(self) -> bool:
        try:
            path = self._token_file()
            tokens = _load_tokens(path)
            tokens = _ensure_fresh_tokens(tokens, path)
            _author_urn(tokens, path)
            return bool(tokens.get("access_token"))
        except (OSError, RuntimeError, json.JSONDecodeError, ValueError):
            return False

    def get_constraints(self) -> dict:
        return {
            "char_limit": 3000,
            "supports_images": True,
            "supports_links": True,
        }

    def render_preview(self, text: str, profile: dict) -> str:
        name = html.escape(profile.get("name", "Your Name"))
        headline = html.escape(profile.get("headline", "Your Headline"))
        pic = profile.get("profile_pic_url", "").strip()
        preview_text = html.escape(text[:210])
        truncated = len(text) > 210

        avatar = (
            f'<img src="{html.escape(pic)}" style="width:48px;height:48px;border-radius:50%;object-fit:cover;" />'
            if pic
            else '<div style="width:48px;height:48px;border-radius:50%;background:#0a66c2;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:600;">in</div>'
        )

        see_more = '<span style="color:#666;">...see more</span>' if truncated else ""
        return f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:552px;border:1px solid #e0e0e0;border-radius:8px;padding:16px;background:#fff;">
          <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px;">
            {avatar}
            <div>
              <div style="font-weight:600;font-size:14px;">{name}</div>
              <div style="font-size:12px;color:#666;">{headline}</div>
            </div>
          </div>
          <div style="font-size:14px;line-height:1.5;white-space:pre-wrap;">{preview_text}{see_more}</div>
          <div style="margin-top:16px;padding-top:8px;border-top:1px solid #eee;font-size:12px;color:#666;">👍 Like · 💬 Comment · ↗ Repost</div>
        </div>
        """

    def publish(self, content: PostContent) -> PublishResult:
        constraints = self.get_constraints()
        char_limit = int(constraints["char_limit"])
        if len(content.text) > char_limit:
            return PublishResult(
                success=False,
                error=f"Post exceeds LinkedIn limit ({len(content.text)}/{char_limit} chars)",
            )

        try:
            token_path = self._token_file()
            tokens = _load_tokens(token_path)
            tokens = _ensure_fresh_tokens(tokens, token_path)
            author = _author_urn(tokens, token_path)
            post_id = _create_post(
                access_token=tokens["access_token"],
                author_urn=author,
                text=content.text,
            )
            return PublishResult(success=True, platform_post_id=post_id)
        except Exception as exc:  # noqa: BLE001 — surface API errors to caller
            return PublishResult(success=False, error=str(exc))
