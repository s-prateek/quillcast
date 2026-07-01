#!/usr/bin/env python3
"""Publish a draft to a configured platform."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from publishers.registry import get  # noqa: E402
from shared.config import enabled_platforms, load_platforms_config  # noqa: E402
from shared.drafts import get_record, update_target_status  # noqa: E402
from shared.env import load_project_env  # noqa: E402
from shared.models import PostContent  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_text(record, platform: str, override: str | None) -> str:
    if override is not None:
        return override.strip()

    target = record.Targets.get(platform)
    if target and target.EditedContent:
        return target.EditedContent.strip()

    variant = record.ContentVariants.get(platform)
    if isinstance(variant, str) and variant.strip():
        return variant.strip()

    raise RuntimeError(f"No content found for platform {platform!r} on draft {record.PostID}")


def publish_draft(
    *,
    post_id: str,
    platform: str,
    text: str | None = None,
    dry_run: bool = False,
) -> dict:
    platforms_config = load_platforms_config()
    enabled = enabled_platforms(platforms_config)
    if platform not in enabled:
        raise RuntimeError(f"Platform {platform!r} is not enabled in config/platforms.yaml")

    record = get_record(post_id)
    if record is None:
        raise RuntimeError(f"Draft not found: {post_id}")

    body = _resolve_text(record, platform, text)
    platform_config = platforms_config.get("platforms", {}).get(platform, {})

    if dry_run:
        return {
            "post_id": post_id,
            "platform": platform,
            "dry_run": True,
            "char_count": len(body),
            "preview": body[:200],
        }

    publisher = get(platform, platform_config=platform_config)
    if not publisher.validate_credentials():
        raise RuntimeError(
            f"Invalid or missing credentials for {platform}. "
            f"Check token file: {platform_config.get('token_file')}"
        )

    result = publisher.publish(PostContent(text=body, platform=platform))
    now = _utc_now()

    if result.success:
        update_target_status(
            post_id,
            platform,
            status="POSTED",
            platform_post_id=result.platform_post_id,
            published_at=now,
            error_log=None,
            edited_content=body if text else None,
            updated_at=now,
        )
        return {
            "post_id": post_id,
            "platform": platform,
            "status": "POSTED",
            "platform_post_id": result.platform_post_id,
        }

    update_target_status(
        post_id,
        platform,
        status="FAILED",
        error_log=result.error,
        edited_content=body if text else None,
        updated_at=now,
    )
    raise RuntimeError(result.error or "Publish failed")


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
