from __future__ import annotations

import streamlit as st

from shared.config import get_llm_provider, list_llm_model_options
from shared.llm import last_invocation
from shared.preferences import get_selected_model_id, set_selected_model_id


def render_llm_model_selector() -> None:
    provider = get_llm_provider()
    models = list_llm_model_options(provider)
    if not models:
        return

    options = {model["id"]: model for model in models}
    current = get_selected_model_id(provider)
    if current not in options:
        current = models[0]["id"]

    def _format_model(model_id: str) -> str:
        entry = options[model_id]
        label = entry["label"]
        note = entry.get("note", "")
        return f"{label} — {note}" if note else label

    selected = st.selectbox(
        "Model",
        options=list(options.keys()),
        index=list(options.keys()).index(current),
        format_func=_format_model,
        key=f"llm_model_select_{provider}",
        help=(
            "Ordered best → fallback. On rate limits, Quillcast automatically tries "
            "the next model in the chain (and the other provider if configured)."
        ),
    )
    if selected != get_selected_model_id(provider):
        set_selected_model_id(selected, provider=provider)

    invocation = last_invocation()
    if invocation.get("fallback_used"):
        st.caption(
            f"Last call used **{invocation.get('provider')}/{invocation.get('model')}** "
            f"(fallback after rate limit)."
        )


def notify_llm_fallback() -> None:
    invocation = last_invocation()
    if invocation.get("fallback_used"):
        model = invocation.get("model", "unknown")
        provider = invocation.get("provider", "")
        st.toast(f"Rate limited — used {provider}/{model} instead.")
