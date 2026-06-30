from __future__ import annotations

import os

import boto3


def resolve_region() -> str:
    """Resolve AWS region from env vars or the active AWS CLI/config profile."""
    for key in ("AWS_REGION", "AWS_DEFAULT_REGION", "CDK_DEFAULT_REGION"):
        value = os.environ.get(key)
        if value:
            return value

    region = boto3.Session().region_name
    if region:
        return region

    raise RuntimeError(
        "No AWS region configured. Run `aws configure set region <region>` "
        "or set AWS_REGION / CDK_DEFAULT_REGION."
    )


def resolve_account_id() -> str | None:
    """Resolve AWS account ID from env vars or STS (returns None if unavailable)."""
    for key in ("CDK_DEFAULT_ACCOUNT", "AWS_ACCOUNT_ID"):
        value = os.environ.get(key)
        if value:
            return value

    try:
        return boto3.Session().client("sts").get_caller_identity()["Account"]
    except Exception:
        return None
