from shared.llm import _normalize_gemini_model, extract_json


def test_extract_json_strips_markdown_fence() -> None:
    text = '```json\n{"linkedin": "hello"}\n```'
    assert extract_json(text) == {"linkedin": "hello"}


def test_normalize_gemini_strips_latest_alias() -> None:
    assert _normalize_gemini_model("gemini-2.5-flash-latest") == "gemini-2.5-flash"
    assert _normalize_gemini_model("gemini-2.5-flash") == "gemini-2.5-flash"
