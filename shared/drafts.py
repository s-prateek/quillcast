from __future__ import annotations

import json
import os
from pathlib import Path

from shared.models import PostRecord, TargetRecord


def _drafts_dir() -> Path:
    configured = os.environ.get("QUILLCAST_DRAFTS_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "data" / "drafts"


def draft_targets_for_platforms(platforms: list[str]) -> dict[str, TargetRecord]:
    return {platform: TargetRecord() for platform in platforms}


def put_record(record: PostRecord) -> None:
    directory = _drafts_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.PostID}.json"
    path.write_text(json.dumps(record.to_item(), indent=2), encoding="utf-8")


def get_record(post_id: str) -> PostRecord | None:
    path = _drafts_dir() / f"{post_id}.json"
    if not path.is_file():
        return None
    item = json.loads(path.read_text(encoding="utf-8"))
    return PostRecord.from_item(item)


def list_records(*, status: str | None = None) -> list[PostRecord]:
    directory = _drafts_dir()
    if not directory.is_dir():
        return []

    records: list[PostRecord] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        item = json.loads(path.read_text(encoding="utf-8"))
        record = PostRecord.from_item(item)
        if status is None or record.OverallStatus == status:
            records.append(record)
    return records


def update_target_status(
    post_id: str,
    platform: str,
    *,
    status: str,
    platform_post_id: str | None = None,
    published_at: str | None = None,
    error_log: str | None = None,
    edited_content: str | None = None,
    updated_at: str,
) -> None:
    record = get_record(post_id)
    if record is None:
        raise ValueError(f"Draft not found: {post_id}")

    target = record.Targets.get(platform)
    if target is None:
        raise ValueError(f"Platform {platform!r} not found on draft {post_id}")

    target.Status = status
    if platform_post_id is not None:
        target.PlatformPostID = platform_post_id
    if published_at is not None:
        target.PublishedAt = published_at
    if error_log is not None:
        target.ErrorLog = error_log
    if edited_content is not None:
        target.EditedContent = edited_content

    record.UpdatedAt = updated_at
    statuses = {t.Status for t in record.Targets.values()}
    if statuses <= {"POSTED", "FAILED", "ARCHIVED"}:
        record.OverallStatus = "COMPLETE"
    else:
        record.OverallStatus = "PENDING"

    put_record(record)
