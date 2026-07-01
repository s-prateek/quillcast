#!/usr/bin/env python3
"""
LinkedIn OAuth helper — run locally to obtain access_token and refresh_token.

Prerequisites:
    export LINKEDIN_CLIENT_ID=...
    export LINKEDIN_CLIENT_SECRET=...

Usage:
    python scripts/linkedin_oauth.py
"""
import json
import os
import secrets
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = ["openid", "profile", "w_member_social"]
DEFAULT_TOKEN_PATH = Path(__file__).resolve().parent.parent / "data" / "tokens" / "linkedin.json"

_captured: dict = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _captured["code"] = params["code"][0]
            _captured["state"] = params.get("state", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authorization successful!</h1>"
                b"<p>You can close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
        else:
            error = params.get("error_description", ["Unknown error"])[0]
            _captured["error"] = error
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"<html><body><h1>Error: {error}</h1></body></html>".encode())

    def log_message(self, format, *args):
        pass


def _token_path() -> Path:
    configured = os.environ.get("LINKEDIN_TOKEN_FILE", "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_TOKEN_PATH


def main():
    client_id = os.environ.get("LINKEDIN_CLIENT_ID")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise SystemExit(
            "ERROR: Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET environment variables."
        )

    state = secrets.token_urlsafe(32)

    auth_params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state,
    })
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{auth_params}"
    print("Opening browser for LinkedIn authorization...")
    print(f"If it doesn't open automatically, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for callback on http://localhost:8080/callback ...")
    server = HTTPServer(("localhost", 8080), _CallbackHandler)
    server.handle_request()

    if "error" in _captured:
        raise SystemExit(f"Authorization failed: {_captured['error']}")

    if not _captured.get("code"):
        raise SystemExit("No authorization code received.")

    if _captured.get("state") != state:
        raise SystemExit("ERROR: State mismatch — possible CSRF attack. Aborting.")

    token_params = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": _captured["code"],
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data=token_params,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        token_response = json.loads(resp.read())

    access_token = token_response["access_token"]
    refresh_token = token_response.get("refresh_token", "")
    expires_in = token_response.get("expires_in", 5184000)
    token_expiry = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()

    token_payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expiry": token_expiry,
    }

    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token_payload, indent=2), encoding="utf-8")

    print(f"\n✅ Tokens saved to {path}")
    print(f"   Token expires: {token_expiry}")
    print(f"   Refresh token present: {'yes' if refresh_token else 'no'}")


if __name__ == "__main__":
    main()
