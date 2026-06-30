from __future__ import annotations

import json
import os
import re
from typing import Any

import boto3

DEFAULT_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
MAX_ATTEMPTS = 2


def _bedrock_client(client=None):
    return client or boto3.client("bedrock-runtime")


def _model_id() -> str:
    return os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)


def _build_prompt(
    *,
    topic: str,
    source_url: str,
    enabled_platforms: list[str],
    voice: dict[str, Any],
) -> tuple[str, str]:
    author_name = voice.get("author_name", "Author")
    description = voice.get("description", "").strip()
    target_audience = voice.get("target_audience", "professionals")

    system_prompt = (
        f"You are a ghostwriter for {author_name}. "
        f"Voice: {description} "
        f"Target audience: {target_audience}."
    )

    platform_specs = {
        "linkedin": '"linkedin": "...",  // max 3000 chars, professional, 3 paragraphs, ends with a question or CTA',
        "facebook": '"facebook": "...",  // max 500 chars, casual, conversational',
        "blog": (
            '"blog": {\n'
            '    "title": "...",\n'
            '    "body": "...",  // full markdown, 600-1200 words\n'
            '    "tags": ["tag1"]\n'
            "  }"
        ),
    }
    schema_lines = [platform_specs[platform] for platform in enabled_platforms if platform in platform_specs]
    schema = "{\n  " + ",\n  ".join(schema_lines) + "\n}"

    user_prompt = (
        f"Topic: {topic}\n"
        f"Source: {source_url}\n\n"
        f"Generate social content as valid JSON for these platforms: {', '.join(enabled_platforms)}\n\n"
        f"{schema}\n\n"
        f"Only include keys for: {', '.join(enabled_platforms)}.\n"
        "Return JSON only with no markdown fences or commentary."
    )
    return system_prompt, user_prompt


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    return json.loads(stripped)


def _invoke_once(
    *,
    system_prompt: str,
    user_prompt: str,
    bedrock_client,
) -> str:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    response = bedrock_client.invoke_model(
        modelId=_model_id(),
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    payload = json.loads(response["body"].read())
    return payload["content"][0]["text"]


def generate_content_variants(
    *,
    topic: str,
    source_url: str,
    enabled_platforms: list[str],
    voice: dict[str, Any],
    bedrock_client=None,
) -> dict[str, Any]:
    if not enabled_platforms:
        raise ValueError("No enabled platforms configured")

    client = _bedrock_client(bedrock_client)
    system_prompt, user_prompt = _build_prompt(
        topic=topic,
        source_url=source_url,
        enabled_platforms=enabled_platforms,
        voice=voice,
    )

    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            text = _invoke_once(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                bedrock_client=client,
            )
            variants = _extract_json(text)
            missing = [platform for platform in enabled_platforms if platform not in variants]
            if missing:
                raise ValueError(f"Missing platform keys in Bedrock response: {missing}")
            return {platform: variants[platform] for platform in enabled_platforms}
        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as exc:
            last_error = exc

    raise RuntimeError("Bedrock returned invalid JSON after retries") from last_error
