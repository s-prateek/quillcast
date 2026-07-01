from __future__ import annotations

from datetime import datetime, timezone

from publishers.registry import get
from shared.config import enabled_platforms, load_platforms_config
from shared.drafts import get_record, update_target_status
from shared.models import PostContent


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_text(record, platform: str, override: str | None) -> str:
    if override is not None:
        return override.strip()

    target = record.Targets.get(platform)
    if target and target.EditedContent:
        return target.EditedContent.strip()

    variant = record.ContentVariants.get(platform)
    if isinstance(variant, str) and variant.strip():
        return variant.strip()

    raise RuntimeError(f"No content found for platform {platform!r} on draft {record.PostID}")


def save_edited_content(*, post_id: str, platform: str, text: str) -> None:
    update_target_status(
        post_id,
        platform,
        status="DRAFT",
        edited_content=text.strip(),
        updated_at=_utc_now(),
    )


def archive_target(*, post_id: str, platform: str) -> None:
    update_target_status(
        post_id,
        platform,
        status="ARCHIVED",
        updated_at=_utc_now(),
    )


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

    body = resolve_text(record, platform, text)
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
            edited_content=body,
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
        edited_content=body,
        updated_at=now,
    )
    raise RuntimeError(result.error or "Publish failed")
