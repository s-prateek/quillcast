from datetime import datetime, timedelta, timezone

from publishers.linkedin import _ensure_fresh_tokens


def test_ensure_fresh_tokens_skips_when_expiry_far_out(tmp_path):
    token_path = tmp_path / "linkedin.json"
    expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    tokens = {
        "access_token": "abc",
        "refresh_token": "def",
        "token_expiry": expiry,
    }

    result = _ensure_fresh_tokens(tokens, token_path)
    assert result is tokens
    assert result["access_token"] == "abc"
