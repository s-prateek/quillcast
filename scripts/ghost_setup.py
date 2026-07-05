#!/usr/bin/env python3
"""
Validate Ghost Admin API credentials from .env.

Add credentials to .env at the project root (see .env.example):
  GHOST_URL=http://localhost:2368
  GHOST_ADMIN_API_KEY=integration_id:integration_secret

Get values from Ghost Admin → Settings → Integrations → Custom integration.

Usage:
    python scripts/ghost_setup.py
    python scripts/ghost_setup.py --url http://localhost:2368 --key id:secret
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from publishers.blog.ghost import GhostPublisher  # noqa: E402
from shared.env import load_project_env  # noqa: E402


def _missing_credentials_message() -> str:
    return (
        "Ghost credentials not configured.\n\n"
        "Add these lines to .env (see .env.example):\n"
        "  GHOST_URL=http://localhost:2368\n"
        "  GHOST_ADMIN_API_KEY=integration_id:integration_secret\n\n"
        "Or pass --url and --key to validate without editing .env."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Ghost Admin API credentials from .env for Quillcast blog publishing"
    )
    parser.add_argument("--url", help="Ghost site URL (overrides .env for this run)")
    parser.add_argument("--key", help="Admin API key id:secret (overrides .env for this run)")
    args = parser.parse_args()

    load_project_env()

    url = (args.url or os.environ.get("GHOST_URL", "")).strip().rstrip("/")
    admin_api_key = (args.key or os.environ.get("GHOST_ADMIN_API_KEY", "")).strip()

    if not url or not admin_api_key:
        print(_missing_credentials_message(), file=sys.stderr)
        sys.exit(1)

    if ":" not in admin_api_key:
        print("ERROR: Admin API key must be in id:secret format.", file=sys.stderr)
        sys.exit(1)

    os.environ["GHOST_URL"] = url
    os.environ["GHOST_ADMIN_API_KEY"] = admin_api_key

    publisher = GhostPublisher()
    if publisher.validate_credentials():
        print("Credentials validated — Ghost Admin API connection OK.")
    else:
        print(
            "WARNING: Could not validate credentials. Check URL/key and that Ghost is running.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
