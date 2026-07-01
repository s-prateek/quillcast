from __future__ import annotations

import streamlit as st

from shared.discover import discover_topics
from shared.generate import generate_post_for_topic, generate_post_from_idea
from shared.models import TopicCandidate


def _init_session_state() -> None:
    if "topic_candidates" not in st.session_state:
        st.session_state.topic_candidates = []
    if "selected_candidate_id" not in st.session_state:
        st.session_state.selected_candidate_id = None


def _candidate_by_id(candidate_id: str) -> TopicCandidate | None:
    for candidate in st.session_state.topic_candidates:
        if candidate.id == candidate_id:
            return candidate
    return None


def _open_draft(post_id: str) -> None:
    st.session_state.selected_draft_id = post_id
    st.session_state.page = "Review"
    st.session_state.topic_candidates = []
    st.session_state.selected_candidate_id = None
    st.success("Draft created — opening editor.")
    st.rerun()


def _render_trending_tab() -> None:
    st.caption("Fetch today's RSS stories, pick one, then generate a draft.")

    if st.button("Fetch trending topics", type="primary", use_container_width=True):
        with st.spinner("Reading RSS feeds and curating topics…"):
            try:
                st.session_state.topic_candidates = discover_topics(use_llm=True)
                st.session_state.selected_candidate_id = None
                st.success(f"Found {len(st.session_state.topic_candidates)} topics.")
            except RuntimeError as exc:
                st.error(str(exc))

    candidates: list[TopicCandidate] = st.session_state.topic_candidates
    if not candidates:
        st.info("Click **Fetch trending topics** to load today's stories from your RSS feeds.")
        return

    st.subheader("Pick a topic")
    option_ids = [candidate.id for candidate in candidates]
    selected_id = st.radio(
        "Topics",
        options=option_ids,
        format_func=lambda cid: next(c.title for c in candidates if c.id == cid),
        label_visibility="collapsed",
        key="discover_topic_radio",
    )
    st.session_state.selected_candidate_id = selected_id

    for candidate in candidates:
        with st.container(border=True):
            st.markdown(f"**{candidate.title}**")
            st.caption(candidate.hook)
            meta = candidate.source_type.upper()
            if candidate.source_url:
                st.markdown(f"{meta} · [source]({candidate.source_url})")
            else:
                st.markdown(meta)

    selected = _candidate_by_id(selected_id)
    if selected is None:
        return

    st.divider()
    if st.button("Generate draft for this topic", type="primary", use_container_width=True):
        with st.spinner("Generating post variants…"):
            try:
                result = generate_post_for_topic(
                    topic=selected.title,
                    source_url=selected.source_url,
                    source_type=selected.source_type,
                )
                _open_draft(result["post_id"])
            except RuntimeError as exc:
                st.error(str(exc))


def _render_custom_idea_tab() -> None:
    st.caption("Describe what you want to share. The LLM will draft posts in your voice.")

    title = st.text_input(
        "Title (optional)",
        placeholder="Short label for your draft list",
        key="custom_idea_title",
    )
    idea = st.text_area(
        "Your idea",
        height=200,
        placeholder=(
            "e.g. I want to write about how we cut deploy time by 40% by moving "
            "integration tests to a dedicated staging pipeline…"
        ),
        key="custom_idea_text",
    )

    if st.button("Generate draft from my idea", type="primary", use_container_width=True):
        if not idea.strip():
            st.warning("Enter your idea before generating a draft.")
            return
        with st.spinner("Generating post variants…"):
            try:
                result = generate_post_from_idea(
                    idea=idea,
                    title=title.strip() or None,
                )
                _open_draft(result["post_id"])
            except RuntimeError as exc:
                st.error(str(exc))


def render_discover_page() -> None:
    _init_session_state()

    st.header("Discover")
    tab_trending, tab_idea = st.tabs(["Trending", "Your idea"])

    with tab_trending:
        _render_trending_tab()

    with tab_idea:
        _render_custom_idea_tab()
