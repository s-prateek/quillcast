import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.config import list_llm_model_options, resolve_model_attempt_order
from shared.llm import LLMAPIError, _invoke_with_model_fallback, _is_rate_limit_error


@pytest.fixture
def llm_config_dir(tmp_path, monkeypatch):
    repo_config = Path(__file__).resolve().parent.parent / "config"
    shutil.copy(repo_config / "llm.example.yaml", tmp_path / "llm.example.yaml")
    monkeypatch.setenv("QUILLCAST_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_list_llm_model_options_ordered_best_first(llm_config_dir):
    models = list_llm_model_options("gemini")
    assert models[0]["id"] == "gemini-3.5-flash"
    assert models[-1]["id"] == "gemini-2.5-flash-lite"


def test_resolve_model_attempt_order_puts_preferred_first(llm_config_dir, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    attempts = resolve_model_attempt_order(preferred_model="gemini-2.5-flash")
    assert attempts[0] == ("gemini", "gemini-2.5-flash")
    assert attempts[1][0] == "gemini"
    assert attempts[1][1] != "gemini-2.5-flash"


def test_is_rate_limit_error_detects_status_codes():
    assert _is_rate_limit_error(LLMAPIError(429, "too many requests"))
    assert _is_rate_limit_error(LLMAPIError(503, "overloaded"))
    assert not _is_rate_limit_error(LLMAPIError(400, "bad request"))


@patch("shared.llm._invoke_provider_model")
@patch("shared.llm.get_selected_model_id", return_value="gemini-2.5-flash")
@patch("shared.llm.get_llm_provider", return_value="gemini")
@patch("shared.llm._provider_has_credentials", return_value=True)
def test_invoke_with_model_fallback_tries_next_on_rate_limit(
    mock_has_creds,
    mock_provider,
    mock_selected,
    mock_invoke,
    llm_config_dir,
    monkeypatch,
):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")

    mock_invoke.side_effect = [
        LLMAPIError(429, "rate limited"),
        "ok response text",
    ]

    text = _invoke_with_model_fallback(system_prompt="sys", user_prompt="user")
    assert text == "ok response text"
    assert mock_invoke.call_count == 2
    assert mock_invoke.call_args_list[0].kwargs["model"] == "gemini-2.5-flash"


@patch("shared.llm._invoke_provider_model")
@patch("shared.llm.get_selected_model_id", return_value="gemini-2.5-flash")
@patch("shared.llm.get_llm_provider", return_value="gemini")
@patch("shared.llm._provider_has_credentials", return_value=True)
def test_invoke_with_model_fallback_raises_when_all_rate_limited(
    mock_has_creds,
    mock_provider,
    mock_selected,
    mock_invoke,
    llm_config_dir,
    monkeypatch,
):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    mock_invoke.side_effect = LLMAPIError(429, "rate limited")

    with pytest.raises(RuntimeError, match="rate limited"):
        _invoke_with_model_fallback(system_prompt="sys", user_prompt="user")

    assert mock_invoke.call_count >= 2
