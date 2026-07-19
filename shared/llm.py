from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any

from shared.config import (
    get_llm_provider,
    resolve_model_attempt_order,
)
from shared.preferences import get_selected_model_id

MAX_ATTEMPTS = 2

logger = logging.getLogger(__name__)

# Google "-latest" aliases often 404 on the REST API; map to stable model ids.
_GEMINI_MODEL_ALIASES = {
    "gemini-3.5-flash-latest": "gemini-3.5-flash",
    "gemini-3-flash-latest": "gemini-3-flash-preview",
    "gemini-2.5-flash-latest": "gemini-2.5-flash",
    "gemini-2.5-pro-latest": "gemini-2.5-pro",
    "gemini-flash-latest": "gemini-3.5-flash",
    "gemini-pro-latest": "gemini-2.5-pro",
}

_RATE_LIMIT_CODES = {429, 503, 529}


class LLMAPIError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"LLM API error {status_code}: {detail}")


_last_invocation: dict[str, Any] = {}


def last_invocation() -> dict[str, Any]:
    """Metadata from the most recent successful LLM call."""
    return dict(_last_invocation)


def _normalize_gemini_model(model: str) -> str:
    normalized = _GEMINI_MODEL_ALIASES.get(model, model)
    if normalized.endswith("-latest"):
        normalized = normalized[: -len("-latest")]
    return normalized


def _provider_has_credentials(provider: str) -> bool:
    if provider == "claude":
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    if provider == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY", "").strip())
    return False


def _is_rate_limit_error(exc: Exception) -> bool:
    if isinstance(exc, LLMAPIError):
        return exc.status_code in _RATE_LIMIT_CODES
    message = str(exc)
    return any(
        token in message
        for token in (" 429", " 503", " 529", "RESOURCE_EXHAUSTED", "rate limit", "Rate limit")
    )


def _voice_prompt_sections(voice: dict[str, Any], *, personality_boost: bool = False) -> str:
    sections: list[str] = []

    avoid = voice.get("avoid_phrases") or []
    if isinstance(avoid, list) and avoid:
        banned = ", ".join(f'"{phrase}"' for phrase in avoid if str(phrase).strip())
        if banned:
            sections.append(f"Never use these phrases or close paraphrases: {banned}.")

    examples = voice.get("voice_examples") or []
    if isinstance(examples, list) and examples:
        sample_lines = [str(ex).strip() for ex in examples if str(ex).strip()]
        if sample_lines:
            joined = "\n---\n".join(sample_lines[:2])
            sections.append(f"Match this tone (do not copy verbatim):\n{joined}")

    sections.append(
        "Vary structure: do not always use three identical paragraphs. "
        "Open with a question, a specific observation, or a contrarian claim when it fits."
    )

    if personality_boost:
        sections.append(
            "Write with noticeably more personality: sharper opinions, a concrete practitioner "
            "moment, varied sentence rhythm. Still authentic — never cheesy or salesy."
        )

    return "\n".join(sections)


def build_prompt(
    *,
    topic: str,
    source_url: str,
    source_type: str = "rss",
    enabled_platforms: list[str],
    voice: dict[str, Any],
    personality_boost: bool = False,
    blog_default_tags: list[str] | None = None,
) -> tuple[str, str]:
    author_name = voice.get("author_name", "Author")
    description = voice.get("description", "").strip()
    target_audience = voice.get("target_audience", "professionals")
    voice_rules = _voice_prompt_sections(voice, personality_boost=personality_boost)

    system_prompt = (
        f"You are a ghostwriter for {author_name}. "
        f"Voice: {description} "
        f"Target audience: {target_audience}. "
        f"{voice_rules}"
    )

    default_tags = blog_default_tags or []
    tags_hint = ""
    if default_tags and "blog" in enabled_platforms:
        tags_hint = f' Prefer tags: {", ".join(default_tags)}.'

    platform_specs = {
        "linkedin": (
            '"linkedin": "...",  // max 3000 chars, 2-4 short paragraphs, '
            "ends with a question or sharp observation"
        ),
        "facebook": '"facebook": "...",  // max 500 chars, casual, conversational',
        "blog": (
            '"blog": {\n'
            '    "title": "...",\n'
            '    "body": "...",  // full markdown, 600-1200 words\n'
            '    "pull_quote": "...",  // optional standout line for the article\n'
            '    "tags": ["tag1"]\n'
            "  }" + (f" //{tags_hint}" if tags_hint else "")
        ),
    }
    schema_lines = [platform_specs[platform] for platform in enabled_platforms if platform in platform_specs]
    schema = "{\n  " + ",\n  ".join(schema_lines) + "\n}"

    if source_type == "custom":
        user_prompt = (
            "The author wants to share their own idea. Develop it into posts — "
            "stay faithful to their angle and key points; do not replace it with a different topic.\n\n"
            f"Author's idea:\n{topic}\n\n"
            f"Generate social content as valid JSON for these platforms: {', '.join(enabled_platforms)}\n\n"
            f"{schema}\n\n"
            f"Only include keys for: {', '.join(enabled_platforms)}.\n"
            "Return JSON only with no markdown fences or commentary."
        )
    else:
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
        raise LLMAPIError(exc.code, detail) from exc


def _invoke_claude(*, model: str, system_prompt: str, user_prompt: str) -> str:
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
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
    )
    return payload["content"][0]["text"]


def _invoke_gemini(*, model: str, system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    normalized = _normalize_gemini_model(model)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{normalized}:generateContent"
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


def _invoke_provider_model(
    *,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    if provider == "claude":
        return _invoke_claude(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    if provider == "gemini":
        return _invoke_gemini(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    raise RuntimeError(f"Unsupported LLM provider: {provider!r}")


def _invoke_with_model_fallback(*, system_prompt: str, user_prompt: str) -> str:
    global _last_invocation

    preferred = get_selected_model_id()
    attempts = resolve_model_attempt_order(
        provider=get_llm_provider(),
        preferred_model=preferred or None,
    )

    rate_limited: list[str] = []
    last_error: Exception | None = None

    for provider, model in attempts:
        if not _provider_has_credentials(provider):
            continue
        try:
            text = _invoke_provider_model(
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            if rate_limited:
                logger.warning(
                    "LLM rate limited on %s — succeeded with %s/%s",
                    ", ".join(rate_limited),
                    provider,
                    model,
                )
            _last_invocation = {
                "provider": provider,
                "model": model,
                "fallback_used": bool(rate_limited),
                "rate_limited_attempts": list(rate_limited),
            }
            return text
        except Exception as exc:
            last_error = exc
            if _is_rate_limit_error(exc):
                rate_limited.append(f"{provider}/{model}")
                logger.warning("LLM rate limited on %s/%s, trying next model", provider, model)
                continue
            raise

    if rate_limited:
        raise RuntimeError(
            "All configured models are rate limited. Tried: "
            + ", ".join(rate_limited)
            + ". Wait a few minutes or switch model in the sidebar."
        ) from last_error
    if last_error:
        raise last_error
    raise RuntimeError("No LLM credentials configured for any provider in the model chain.")


def generate_content_variants(
    *,
    topic: str,
    source_url: str,
    source_type: str = "rss",
    enabled_platforms: list[str],
    voice: dict[str, Any],
    personality_boost: bool = False,
    blog_default_tags: list[str] | None = None,
) -> dict[str, Any]:
    if not enabled_platforms:
        raise ValueError("No enabled platforms configured")

    system_prompt, user_prompt = build_prompt(
        topic=topic,
        source_url=source_url,
        source_type=source_type,
        enabled_platforms=enabled_platforms,
        voice=voice,
        personality_boost=personality_boost,
        blog_default_tags=blog_default_tags,
    )

    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            text = _invoke_with_model_fallback(system_prompt=system_prompt, user_prompt=user_prompt)
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
    persona: dict[str, Any] | None = None,
    max_topics: int = 12,
    exclude_titles: list[str] | None = None,
) -> list[Any]:
    """LLM call #1 — rank RSS + evergreen into post-worthy topic cards."""
    from shared.models import TopicCandidate

    author_name = voice.get("author_name", "Author")
    description = voice.get("description", "").strip()
    target_audience = voice.get("target_audience", "professionals")
    curation_hint = ""
    if persona:
        curation_hint = str(persona.get("curation_hint", "")).strip()

    article_lines = []
    for index, article in enumerate(articles):
        summary = _strip_html(getattr(article, "summary", ""))[:280]
        article_lines.append(
            f'{index}. title={article.title!r} url={article.url!r} summary={summary!r}'
        )

    evergreen_lines = [f'- {topic!r}' for topic in evergreen_topics]

    exclude_block = ""
    if exclude_titles:
        excluded = [title.strip() for title in exclude_titles if title.strip()]
        if excluded:
            exclude_block = (
                "\nDo not repeat these topics already shown to the author:\n"
                + "\n".join(f"- {title}" for title in excluded)
                + "\n"
            )

    hint_block = f"\nEditorial angle: {curation_hint}\n" if curation_hint else ""
    system_prompt = (
        f"You are an editorial assistant for {author_name}. "
        f"Voice: {description} Target audience: {target_audience}. "
        "Pick topics worth posting today."
        f"{hint_block}"
    )
    user_prompt = (
        "From the RSS articles and evergreen ideas below, return up to "
        f"{max_topics} post-worthy topics as JSON.\n\n"
        "RSS articles:\n"
        + ("\n".join(article_lines) if article_lines else "(none)")
        + "\n\nEvergreen ideas:\n"
        + ("\n".join(evergreen_lines) if evergreen_lines else "(none)")
        + exclude_block
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
            text = _invoke_with_model_fallback(system_prompt=system_prompt, user_prompt=user_prompt)
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
