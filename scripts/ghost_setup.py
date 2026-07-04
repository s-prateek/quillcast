#!/usr/bin/env python3
"""
Save Ghost Admin API credentials to .env for Quillcast blog publishing.

Get credentials from Ghost Admin → Settings → Integrations → Custom integration:
  - API URL (site root, e.g. http://localhost:2368 or https://yourblog.com)
  - Admin API key (format id:secret)

Usage:
    python scripts/ghost_setup.py
    python scripts/ghost_setup.py --url http://localhost:2368 --key id:secret
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from publishers.blog.ghost import GhostPublisher  # noqa: E402
from shared.env_file import project_env_path, upsert_env_vars  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure Ghost Admin API credentials for Quillcast")
    parser.add_argument("--url", help="Ghost site URL (e.g. http://localhost:2368)")
    parser.add_argument("--key", help="Admin API key (id:secret)")
    parser.add_argument(
        "--env-file",
        default=str(project_env_path()),
        help="Path to .env file (default: project root .env)",
    )
    args = parser.parse_args()

    url = (args.url or input("Ghost API URL [http://localhost:2368]: ").strip()) or "http://localhost:2368"
    if args.key:
        admin_api_key = args.key.strip()
    else:
        admin_api_key = getpass.getpass("Admin API key (id:secret): ").strip()

    if not admin_api_key or ":" not in admin_api_key:
        print("ERROR: Admin API key must be in id:secret format.", file=sys.stderr)
        sys.exit(1)

    env_path = Path(args.env_file)
    if not env_path.is_absolute():
        env_path = ROOT / env_path

    upsert_env_vars(
        env_path,
        {
            "GHOST_URL": url.rstrip("/"),
            "GHOST_ADMIN_API_KEY": admin_api_key,
        },
    )
    print(f"Saved credentials to {env_path}")

    os.environ["GHOST_URL"] = url.rstrip("/")
    os.environ["GHOST_ADMIN_API_KEY"] = admin_api_key

    publisher = GhostPublisher()
    if publisher.validate_credentials():
        print("Credentials validated — Ghost Admin API connection OK.")
        print("Restart Streamlit if it is already running so it reloads .env.")
    else:
        print(
            "WARNING: Could not validate credentials. Check URL/key and that Ghost is running.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
