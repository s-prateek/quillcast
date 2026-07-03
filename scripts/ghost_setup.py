#!/usr/bin/env python3
"""
Save Ghost Admin API credentials for Quillcast blog publishing.

Get credentials from Ghost Admin → Settings → Integrations → Custom integration:
  - API URL (site root, e.g. http://localhost:2368 or https://yourblog.com)
  - Admin API key (format id:secret)

Usage:
    python scripts/ghost_setup.py
    python scripts/ghost_setup.py --url http://localhost:2368 --key id:secret
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from publishers.blog.ghost import GhostPublisher  # noqa: E402

DEFAULT_TOKEN_PATH = ROOT / "data" / "tokens" / "blog.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure Ghost Admin API credentials for Quillcast")
    parser.add_argument("--url", help="Ghost site URL (e.g. http://localhost:2368)")
    parser.add_argument("--key", help="Admin API key (id:secret)")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_TOKEN_PATH),
        help=f"Token file path (default: {DEFAULT_TOKEN_PATH})",
    )
    args = parser.parse_args()

    url = (args.url or input("Ghost API URL [http://localhost:2368]: ").strip()) or "http://localhost:2368"
    admin_api_key = args.key or input("Admin API key (id:secret): ").strip()

    if not admin_api_key or ":" not in admin_api_key:
        print("ERROR: Admin API key must be in id:secret format.", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output

    payload = {
        "url": url.rstrip("/"),
        "admin_api_key": admin_api_key,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Saved credentials to {output}")

    publisher = GhostPublisher(platform_config={"token_file": str(output.relative_to(ROOT))})
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
