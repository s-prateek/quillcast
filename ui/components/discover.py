from __future__ import annotations

import streamlit as st

from shared.config import get_persona, list_personas
from shared.discover import discover_topics
from shared.generate import generate_post_for_topic, generate_post_from_idea
from shared.models import TopicCandidate
from shared.preferences import get_active_persona_id, set_active_persona_id
from ui.components.llm_selector import notify_llm_fallback


def _init_session_state() -> None:
    if "topic_candidates" not in st.session_state:
        st.session_state.topic_candidates = []
    if "selected_candidate_id" not in st.session_state:
        st.session_state.selected_candidate_id = None
    if "active_persona_id" not in st.session_state:
        st.session_state.active_persona_id = get_active_persona_id()


def _persona_selector() -> str:
    personas = list_personas()
    if not personas:
        raise RuntimeError("No personas configured. Add entries to config/personas.yaml")

    options = {p["id"]: p["label"] for p in personas}
    current = st.session_state.active_persona_id
    if current not in options:
        current = get_active_persona_id()

    selected = st.selectbox(
        "Persona",
        options=list(options.keys()),
        index=list(options.keys()).index(current),
        format_func=lambda pid: options[pid],
        key="discover_persona_select",
    )
    if selected != st.session_state.active_persona_id:
        st.session_state.active_persona_id = selected
        set_active_persona_id(selected)
        st.session_state.topic_candidates = []
        st.session_state.selected_candidate_id = None

    persona = get_persona(selected)
    st.caption(persona.get("voice", {}).get("target_audience", ""))
    return selected


def _candidate_by_id(candidate_id: str) -> TopicCandidate | None:
    for candidate in st.session_state.topic_candidates:
        if candidate.id == candidate_id:
            return candidate
    return None


def _merge_topic_candidates(
    existing: list[TopicCandidate],
    new_candidates: list[TopicCandidate],
) -> list[TopicCandidate]:
    seen = {candidate.title.strip().lower() for candidate in existing}
    merged = list(existing)
    next_index = len(existing)
    for candidate in new_candidates:
        key = candidate.title.strip().lower()
        if not key or key in seen:
            continue
        merged.append(
            TopicCandidate(
                id=f"topic-{next_index}",
                title=candidate.title,
                hook=candidate.hook,
                source_url=candidate.source_url,
                source_type=candidate.source_type,
            )
        )
        seen.add(key)
        next_index += 1
    return merged


def _open_draft(post_id: str) -> None:
    st.session_state.selected_draft_id = post_id
    st.session_state.page = "Review"
    st.session_state.topic_candidates = []
    st.session_state.selected_candidate_id = None
    st.success("Draft created — opening editor.")
    st.rerun()


def _fetch_topics(persona_id: str, *, append: bool) -> None:
    existing = st.session_state.topic_candidates if append else []
    exclude_titles = [candidate.title for candidate in existing]
    with st.spinner("Reading RSS feeds and curating topics…"):
        new_candidates = discover_topics(
            persona_id=persona_id,
            use_llm=True,
            exclude_titles=exclude_titles or None,
        )
        if append:
            st.session_state.topic_candidates = _merge_topic_candidates(existing, new_candidates)
        else:
            st.session_state.topic_candidates = new_candidates
            st.session_state.selected_candidate_id = None
    notify_llm_fallback()


def _render_trending_tab(persona_id: str) -> None:
    st.caption("Fetch today's RSS stories for this persona, pick one, then generate a draft.")

    fetch_cols = st.columns(2)
    with fetch_cols[0]:
        if st.button("Fetch trending topics", type="primary", use_container_width=True):
            try:
                _fetch_topics(persona_id, append=False)
                st.success(f"Found {len(st.session_state.topic_candidates)} topics.")
            except RuntimeError as exc:
                st.error(str(exc))

    with fetch_cols[1]:
        has_candidates = bool(st.session_state.topic_candidates)
        if st.button(
            "Fetch more ideas",
            use_container_width=True,
            disabled=not has_candidates,
            help="Load additional topics without clearing the current list",
        ):
            try:
                before = len(st.session_state.topic_candidates)
                _fetch_topics(persona_id, append=True)
                added = len(st.session_state.topic_candidates) - before
                if added:
                    st.success(f"Added {added} more topics.")
                else:
                    st.info("No new topics found — try again later or adjust your RSS feeds.")
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
                    persona_id=persona_id,
                )
                _open_draft(result["post_id"])
            except RuntimeError as exc:
                st.error(str(exc))


def _render_custom_idea_tab(persona_id: str) -> None:
    st.caption("Describe what you want to share. The LLM will draft posts in your persona's voice.")

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
                    persona_id=persona_id,
                )
                _open_draft(result["post_id"])
            except RuntimeError as exc:
                st.error(str(exc))


def render_discover_page() -> None:
    _init_session_state()

    st.header("Discover")
    persona_id = _persona_selector()

    tab_trending, tab_idea = st.tabs(["Trending", "Your idea"])

    with tab_trending:
        _render_trending_tab(persona_id)

    with tab_idea:
        _render_custom_idea_tab(persona_id)
