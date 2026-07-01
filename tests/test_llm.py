from shared.llm import extract_json


def test_extract_json_strips_markdown_fence() -> None:
    text = '```json\n{"linkedin": "hello"}\n```'
    assert extract_json(text) == {"linkedin": "hello"}
