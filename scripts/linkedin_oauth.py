#!/usr/bin/env python3
"""
LinkedIn OAuth helper — run this locally to obtain access_token and refresh_token
and store them in AWS SSM Parameter Store.

Prerequisites:
    pip install boto3
    export LINKEDIN_CLIENT_ID=...
    export LINKEDIN_CLIENT_SECRET=...
    export AWS_REGION=us-east-1  (or your region)

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

import boto3

REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = ["openid", "profile", "w_member_social"]

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
        pass  # suppress request logs


def main():
    client_id = os.environ.get("LINKEDIN_CLIENT_ID")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET")
    region = os.environ.get("AWS_REGION", "us-east-1")

    if not client_id or not client_secret:
        raise SystemExit(
            "ERROR: Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET environment variables."
        )

    # CSRF protection via state parameter
    state = secrets.token_urlsafe(32)

    # Step 1: Open browser for authorization
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

    # Step 2: Capture the callback
    print("Waiting for callback on http://localhost:8080/callback ...")
    server = HTTPServer(("localhost", 8080), _CallbackHandler)
    server.handle_request()

    if "error" in _captured:
        raise SystemExit(f"Authorization failed: {_captured['error']}")

    if not _captured.get("code"):
        raise SystemExit("No authorization code received.")

    # Validate CSRF state
    if _captured.get("state") != state:
        raise SystemExit("ERROR: State mismatch — possible CSRF attack. Aborting.")

    # Step 3: Exchange auth code for tokens
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
    expires_in = token_response.get("expires_in", 5184000)  # default: 60 days
    token_expiry = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()

    token_payload = json.dumps({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expiry": token_expiry,
    })

    # Step 4: Store in SSM as SecureString (encrypted at rest, free with AWS managed key)
    ssm = boto3.client("ssm", region_name=region)
    ssm.put_parameter(
        Name="/quillcast/linkedin/tokens",
        Value=token_payload,
        Type="SecureString",
        Overwrite=True,
    )

    print("\n✅ Tokens stored in SSM: /quillcast/linkedin/tokens")
    print(f"   Token expires: {token_expiry}")
    print(f"   Refresh token present: {'yes' if refresh_token else 'no'}")


if __name__ == "__main__":
    main()
