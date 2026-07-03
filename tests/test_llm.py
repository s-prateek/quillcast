from shared.llm import _normalize_gemini_model, build_prompt, extract_json
from shared.generate import _topic_label_from_idea


def test_extract_json_strips_markdown_fence() -> None:
    text = '```json\n{"linkedin": "hello"}\n```'
    assert extract_json(text) == {"linkedin": "hello"}


def test_normalize_gemini_strips_latest_alias() -> None:
    assert _normalize_gemini_model("gemini-2.5-flash-latest") == "gemini-2.5-flash"
    assert _normalize_gemini_model("gemini-2.5-flash") == "gemini-2.5-flash"


def test_build_prompt_custom_idea_uses_author_idea_wording() -> None:
    _, user_prompt = build_prompt(
        topic="My hot take on monoliths",
        source_url="",
        source_type="custom",
        enabled_platforms=["linkedin"],
        voice={"author_name": "Test", "description": "Direct", "target_audience": "engineers"},
    )
    assert "Author's idea:" in user_prompt
    assert "My hot take on monoliths" in user_prompt
    assert "Topic:" not in user_prompt


def test_topic_label_from_idea_prefers_title() -> None:
    assert _topic_label_from_idea("long body text", title="Short title") == "Short title"


def test_topic_label_from_idea_uses_first_line() -> None:
    assert _topic_label_from_idea("First line\nSecond line") == "First line"
