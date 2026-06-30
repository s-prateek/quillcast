import json

from bedrock import _extract_json, generate_content_variants


def test_extract_json_strips_markdown_fence():
    payload = {"linkedin": "Hello world"}
    text = f"```json\n{json.dumps(payload)}\n```"

    assert _extract_json(text) == payload


def test_generate_content_variants_uses_bedrock_response():
    class FakeBody:
        def read(self):
            return json.dumps(
                {"content": [{"text": json.dumps({"linkedin": "Generated post"})}]}
            ).encode()

    class FakeClient:
        def invoke_model(self, **kwargs):
            assert kwargs["modelId"]
            return {"body": FakeBody()}

    variants = generate_content_variants(
        topic="Shipping side projects",
        source_url="evergreen",
        enabled_platforms=["linkedin"],
        voice={"author_name": "Test Author"},
        bedrock_client=FakeClient(),
    )

    assert variants == {"linkedin": "Generated post"}
