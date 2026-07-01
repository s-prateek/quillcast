from __future__ import annotations

from typing import Any

import boto3

from shared.models import PostRecord, TargetRecord


def _table(table_name: str, dynamodb=None):
    resource = dynamodb or boto3.resource("dynamodb")
    return resource.Table(table_name)


def put_record(table_name: str, record: PostRecord, *, dynamodb=None) -> None:
    _table(table_name, dynamodb).put_item(Item=record.to_item())


def get_record(table_name: str, post_id: str, *, dynamodb=None) -> PostRecord | None:
    response = _table(table_name, dynamodb).get_item(Key={"PostID": post_id})
    item = response.get("Item")
    if not item:
        return None
    return PostRecord.from_item(item)


def update_target_status(
    table_name: str,
    post_id: str,
    platform: str,
    *,
    status: str,
    platform_post_id: str | None = None,
    published_at: str | None = None,
    error_log: str | None = None,
    edited_content: str | None = None,
    updated_at: str,
    dynamodb=None,
) -> None:
    expression_parts = ["#targets.#platform.#status = :status", "UpdatedAt = :updated_at"]
    names: dict[str, str] = {
        "#targets": "Targets",
        "#platform": platform,
        "#status": "Status",
    }
    values: dict[str, Any] = {
        ":status": status,
        ":updated_at": updated_at,
    }

    if platform_post_id is not None:
        expression_parts.append("#targets.#platform.PlatformPostID = :platform_post_id")
        values[":platform_post_id"] = platform_post_id

    if published_at is not None:
        expression_parts.append("#targets.#platform.PublishedAt = :published_at")
        values[":published_at"] = published_at

    if error_log is not None:
        expression_parts.append("#targets.#platform.ErrorLog = :error_log")
        values[":error_log"] = error_log

    if edited_content is not None:
        expression_parts.append("#targets.#platform.EditedContent = :edited_content")
        values[":edited_content"] = edited_content

    _table(table_name, dynamodb).update_item(
        Key={"PostID": post_id},
        UpdateExpression="SET " + ", ".join(expression_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def draft_targets_for_platforms(platforms: list[str]) -> dict[str, TargetRecord]:
    return {platform: TargetRecord() for platform in platforms}
