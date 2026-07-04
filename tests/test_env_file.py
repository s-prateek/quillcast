from shared.env_file import upsert_env_vars


def test_upsert_env_vars_creates_file(tmp_path):
    env_path = tmp_path / ".env"
    upsert_env_vars(env_path, {"GHOST_URL": "http://localhost:2368", "GHOST_ADMIN_API_KEY": "id:abc123"})
    text = env_path.read_text(encoding="utf-8")
    assert "GHOST_URL=http://localhost:2368" in text
    assert "GHOST_ADMIN_API_KEY=id:abc123" in text
    assert oct(env_path.stat().st_mode & 0o777) == oct(0o600)


def test_upsert_env_vars_replaces_existing_keys(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("ANTHROPIC_API_KEY=sk-test\nGHOST_URL=http://old\n", encoding="utf-8")
    upsert_env_vars(env_path, {"GHOST_URL": "http://localhost:2368"})
    text = env_path.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=sk-test" in text
    assert "GHOST_URL=http://localhost:2368" in text
    assert "http://old" not in text
