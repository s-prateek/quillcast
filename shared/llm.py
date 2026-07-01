from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

MAX_ATTEMPTS = 2

DEFAULT_CLAUDE_MODEL = "claude-3-5-haiku-latest"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

# Google 2.5 "-latest" aliases often 404 on the REST API; use stable base names.
_GEMINI_MODEL_ALIASES = {
    "gemini-2.5-flash-latest": "gemini-2.5-flash",
    "gemini-2.5-pro-latest": "gemini-2.5-pro",
    "gemini-flash-latest": "gemini-2.5-flash",
    "gemini-pro-latest": "gemini-2.5-pro",
}


def _normalize_gemini_model(model: str) -> str:
    normalized = _GEMINI_MODEL_ALIASES.get(model, model)
    if normalized.endswith("-latest"):
        normalized = normalized[: -len("-latest")]
    return normalized


def _provider() -> str:
    name = os.environ.get("LLM_PROVIDER", "claude").strip().lower()
    if name not in {"claude", "gemini"}:
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {name!r} (use 'claude' or 'gemini')")
    return name


def _model_id() -> str:
    override = os.environ.get("LLM_MODEL", "").strip()
    if _provider() == "gemini":
        if override:
            return _normalize_gemini_model(override)
        return DEFAULT_GEMINI_MODEL
    if override:
        return override
    return DEFAULT_CLAUDE_MODEL


def build_prompt(
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


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return json.loads(stripped)


def _http_post_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API error {exc.code}: {detail}") from exc


def _invoke_claude(*, system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    payload = _http_post_json(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        body={
            "model": _model_id(),
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
    )
    return payload["content"][0]["text"]


def _invoke_gemini(*, system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model = _model_id()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    payload = _http_post_json(
        url,
        headers={},
        body={
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": 4096},
        },
    )
    return payload["candidates"][0]["content"]["parts"][0]["text"]


def _invoke_once(*, system_prompt: str, user_prompt: str) -> str:
    if _provider() == "claude":
        return _invoke_claude(system_prompt=system_prompt, user_prompt=user_prompt)
    return _invoke_gemini(system_prompt=system_prompt, user_prompt=user_prompt)


def generate_content_variants(
    *,
    topic: str,
    source_url: str,
    enabled_platforms: list[str],
    voice: dict[str, Any],
) -> dict[str, Any]:
    if not enabled_platforms:
        raise ValueError("No enabled platforms configured")

    system_prompt, user_prompt = build_prompt(
        topic=topic,
        source_url=source_url,
        enabled_platforms=enabled_platforms,
        voice=voice,
    )

    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            text = _invoke_once(system_prompt=system_prompt, user_prompt=user_prompt)
            variants = extract_json(text)
            missing = [platform for platform in enabled_platforms if platform not in variants]
            if missing:
                raise ValueError(f"Missing platform keys in LLM response: {missing}")
            return {platform: variants[platform] for platform in enabled_platforms}
        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as exc:
            last_error = exc

    raise RuntimeError("LLM returned invalid JSON after retries") from last_error


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def curate_topic_candidates(
    *,
    articles: list[Any],
    evergreen_topics: list[str],
    voice: dict[str, Any],
    max_topics: int = 8,
) -> list[Any]:
    """LLM call #1 — rank RSS + evergreen into post-worthy topic cards."""
    from shared.models import TopicCandidate

    author_name = voice.get("author_name", "Author")
    description = voice.get("description", "").strip()
    target_audience = voice.get("target_audience", "professionals")

    article_lines = []
    for index, article in enumerate(articles):
        summary = _strip_html(getattr(article, "summary", ""))[:280]
        article_lines.append(
            f'{index}. title={article.title!r} url={article.url!r} summary={summary!r}'
        )

    evergreen_lines = [f'- {topic!r}' for topic in evergreen_topics]

    system_prompt = (
        f"You are an editorial assistant for {author_name}. "
        f"Voice: {description} Target audience: {target_audience}. "
        "Pick topics worth a LinkedIn post today."
    )
    user_prompt = (
        "From the RSS articles and evergreen ideas below, return up to "
        f"{max_topics} post-worthy topics as JSON.\n\n"
        "RSS articles:\n"
        + ("\n".join(article_lines) if article_lines else "(none)")
        + "\n\nEvergreen ideas:\n"
        + ("\n".join(evergreen_lines) if evergreen_lines else "(none)")
        + "\n\nReturn JSON only:\n"
        "{\n"
        '  "topics": [\n'
        "    {\n"
        '      "title": "short post topic title",\n'
        '      "hook": "1-2 sentences on why this is worth posting today",\n'
        '      "source_url": "article url or empty string for evergreen",\n'
        '      "source_type": "rss or evergreen"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Prefer fresh RSS stories when available. Include at most 2 evergreen options."
    )

    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            text = _invoke_once(system_prompt=system_prompt, user_prompt=user_prompt)
            payload = extract_json(text)
            raw_topics = payload.get("topics", payload if isinstance(payload, list) else [])
            candidates: list[TopicCandidate] = []
            for index, item in enumerate(raw_topics[:max_topics]):
                source_url = (item.get("source_url") or "").strip()
                source_type = (item.get("source_type") or ("rss" if source_url else "evergreen")).strip()
                title = (item.get("title") or "").strip()
                hook = (item.get("hook") or "").strip()
                if not title:
                    continue
                candidates.append(
                    TopicCandidate(
                        id=f"topic-{index}",
                        title=title,
                        hook=hook or title,
                        source_url=source_url,
                        source_type=source_type,
                    )
                )
            if candidates:
                return candidates
            raise ValueError("LLM returned no usable topics")
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            last_error = exc

    raise RuntimeError("LLM returned invalid topic JSON after retries") from last_error
