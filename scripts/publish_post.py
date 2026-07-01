#!/usr/bin/env python3
"""Publish a draft to a configured platform."""

from __future__ import annotations

import argparse
import sys

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from shared.env import load_project_env  # noqa: E402
from shared.publish import publish_draft  # noqa: E402


def main() -> None:
    load_project_env()

    parser = argparse.ArgumentParser(description="Publish a Quillcast draft to a platform")
    parser.add_argument("--post-id", required=True, help="Draft PostID (UUID)")
    parser.add_argument("--platform", default="linkedin", help="Platform name (default: linkedin)")
    parser.add_argument("--text", help="Override post text (default: draft content)")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show content without posting")
    args = parser.parse_args()

    try:
        outcome = publish_draft(
            post_id=args.post_id,
            platform=args.platform,
            text=args.text,
            dry_run=args.dry_run,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(outcome)


if __name__ == "__main__":
    main()
