from shared.publish import build_post_content


def test_build_post_content_resolves_ghost_template_from_persona(monkeypatch, tmp_path):
    (tmp_path / "platforms.example.yaml").write_text(
        """
platforms:
  blog:
    enabled: false
    default_status: draft
    ghost_custom_templates:
      by_tag: {}
      by_persona: {}
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "personas.example.yaml").write_text(
        """
default_persona: games
personas:
  games:
    label: Games
    voice:
      author_name: Test
      description: Voice
      target_audience: Gamers
    blog_defaults:
      ghost_custom_template: custom-games
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))

    body = '{"title": "Post", "body": "Hello", "tags": ["Nintendo"]}'
    content = build_post_content(
        platform="blog",
        body=body,
        platform_config={"default_status": "draft"},
        persona_id="games",
    )
    assert content.metadata.get("ghost_custom_template") == "custom-games"
