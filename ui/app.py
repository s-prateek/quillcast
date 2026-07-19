from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.config import (  # noqa: E402
    get_persona,
    list_personas,
    load_platforms_config,
    persona_platforms,
    resolve_author_name,
)
from shared.drafts import delete_record, get_record, list_records  # noqa: E402
from shared.env import load_project_env  # noqa: E402
from shared.generate import (  # noqa: E402
    generate_platform_content,
    regenerate_draft_content,
    regenerate_draft_from_source,
    update_draft_source,
)
from ui.components.discover import render_discover_page  # noqa: E402
from ui.components.llm_selector import notify_llm_fallback, render_llm_model_selector  # noqa: E402
from ui.components.platform_tab import render_platform_tab  # noqa: E402

load_project_env()

st.set_page_config(page_title="Quillcast", page_icon="🪶", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "Discover"
if "selected_draft_id" not in st.session_state:
    st.session_state.selected_draft_id = None
if "confirm_delete_draft_id" not in st.session_state:
    st.session_state.confirm_delete_draft_id = None


def _author_profile(persona_id: str) -> dict[str, str]:
    persona = get_persona(persona_id)
    voice = persona.get("voice", {})
    return {
        "name": resolve_author_name(persona),
        "headline": os.environ.get("AUTHOR_HEADLINE", voice.get("headline", "Your Headline")),
        "profile_pic_url": os.environ.get("AUTHOR_PROFILE_PIC_URL", ""),
    }


def _persona_label(persona_id: str) -> str:
    for persona in list_personas():
        if persona["id"] == persona_id:
            return persona["label"]
    return persona_id


def _pending_drafts():
    return list_records(status="PENDING")


def _draft_label(record) -> str:
    topic = record.Topic[:40] + ("…" if len(record.Topic) > 40 else "")
    date = record.CreatedAt[:10]
    persona = _persona_label(record.PersonaID)
    return f"{topic} · {persona} · {date}"


def _delete_draft(post_id: str) -> None:
    if delete_record(post_id):
        if st.session_state.selected_draft_id == post_id:
            st.session_state.selected_draft_id = None
        st.session_state.confirm_delete_draft_id = None
        st.toast("Draft deleted.")
        st.rerun()
    st.error("Draft not found.")


def _render_custom_idea_editor(record) -> None:
    with st.expander("Your idea", expanded=False):
        st.caption("Correct the source idea and regenerate drafts if the AI misunderstood.")
        idea = st.text_area(
            "Source idea",
            value=record.SourceContent,
            height=160,
            key=f"review-idea-{record.PostID}",
            label_visibility="collapsed",
        )
        title = st.text_input(
            "Draft title (optional)",
            value=record.Topic,
            key=f"review-idea-title-{record.PostID}",
        )

        regen_cols = st.columns(2)
        with regen_cols[0]:
            if st.button(
                "Regenerate from updated idea",
                key=f"regen-idea-{record.PostID}",
                use_container_width=True,
            ):
                if not idea.strip():
                    st.warning("Idea cannot be empty.")
                else:
                    with st.spinner("Regenerating drafts from your updated idea…"):
                        try:
                            regenerate_draft_from_source(
                                post_id=record.PostID,
                                idea=idea,
                                title=title.strip() or None,
                            )
                            notify_llm_fallback()
                            st.toast("Drafts regenerated.")
                            st.rerun()
                        except RuntimeError as exc:
                            st.error(str(exc))

        with regen_cols[1]:
            if st.button(
                "Save idea only",
                key=f"save-idea-{record.PostID}",
                use_container_width=True,
            ):
                if not idea.strip():
                    st.warning("Idea cannot be empty.")
                else:
                    try:
                        update_draft_source(
                            post_id=record.PostID,
                            idea=idea,
                            title=title.strip() or None,
                        )
                        st.toast("Idea saved.")
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))


def _render_ungenerated_platform_tab(record, platform: str) -> None:
    st.info(f"No {platform} draft yet. Generate one when you're ready.")
    if st.button(
        f"Generate {platform} draft",
        key=f"generate-{record.PostID}-{platform}",
        type="primary",
        use_container_width=True,
    ):
        with st.spinner(f"Generating {platform} draft…"):
            try:
                generate_platform_content(post_id=record.PostID, platform=platform)
                notify_llm_fallback()
                st.toast(f"{platform.capitalize()} draft generated.")
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))


def _render_review_page(platforms_config: dict) -> None:
    pending = _pending_drafts()

    with st.sidebar:
        st.header("Pending drafts")
        if not pending:
            st.info("No pending drafts. Use **Discover** to fetch topics and generate one.")
            return

        labels = {record.PostID: _draft_label(record) for record in pending}
        default_id = st.session_state.selected_draft_id
        if default_id not in labels:
            default_id = pending[0].PostID

        selected_id = st.radio(
            "Select a draft",
            options=list(labels.keys()),
            index=list(labels.keys()).index(default_id),
            format_func=lambda post_id: labels[post_id],
            label_visibility="collapsed",
        )
        st.session_state.selected_draft_id = selected_id

        st.divider()
        if st.session_state.confirm_delete_draft_id == selected_id:
            st.warning("Delete this draft permanently?")
            confirm_cols = st.columns(2)
            with confirm_cols[0]:
                if st.button("Yes, delete", key="confirm-delete-draft", type="primary"):
                    _delete_draft(selected_id)
            with confirm_cols[1]:
                if st.button("Cancel", key="cancel-delete-draft"):
                    st.session_state.confirm_delete_draft_id = None
                    st.rerun()
        elif st.button("Delete draft", key="delete-draft-btn"):
            st.session_state.confirm_delete_draft_id = selected_id
            st.rerun()

    record = get_record(selected_id)
    if record is None:
        st.error("Draft not found.")
        return

    header_cols = st.columns([3, 1])
    with header_cols[0]:
        st.subheader(record.Topic)
    with header_cols[1]:
        st.markdown(f"**{_persona_label(record.PersonaID)}**")

    meta_cols = st.columns(2)
    with meta_cols[0]:
        st.caption(f"Created {record.CreatedAt}")
    with meta_cols[1]:
        if record.SourceURL:
            st.caption(f"Source: [{record.SourceType}]({record.SourceURL})")
        else:
            st.caption(f"Source: {record.SourceType}")

    if record.SourceType == "custom":
        _render_custom_idea_editor(record)

    action_cols = st.columns([1, 3])
    with action_cols[0]:
        if st.button("More personality", help="Re-draft generated platforms with stronger voice"):
            with st.spinner("Regenerating with more personality…"):
                try:
                    regenerate_draft_content(post_id=record.PostID, personality_boost=True)
                    notify_llm_fallback()
                    st.toast("Draft regenerated.")
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

    profile = _author_profile(record.PersonaID)
    persona_enabled = persona_platforms(record.PersonaID)
    tab_platforms = [platform for platform in persona_enabled if platform in record.Targets]
    if not tab_platforms:
        st.warning("This draft has no platform targets.")
        return

    def _tab_label(platform: str) -> str:
        label = platform.capitalize()
        if platform not in record.ContentVariants:
            return f"{label} · not generated"
        return label

    tabs = st.tabs([_tab_label(platform) for platform in tab_platforms])
    for platform, tab in zip(tab_platforms, tabs):
        with tab:
            if platform not in record.ContentVariants:
                _render_ungenerated_platform_tab(record, platform)
                continue

            platform_config = platforms_config.get("platforms", {}).get(platform, {})
            render_platform_tab(
                record,
                platform,
                platform_config=platform_config,
                profile=profile,
            )


def main() -> None:
    st.title("Quillcast")
    st.caption("Discover topics, draft posts, review, and publish.")

    platforms_config = load_platforms_config()

    with st.sidebar:
        st.session_state.page = st.radio(
            "Navigate",
            options=["Discover", "Review"],
            index=0 if st.session_state.page == "Discover" else 1,
            label_visibility="collapsed",
        )
        st.divider()
        render_llm_model_selector()

    if st.session_state.page == "Discover":
        render_discover_page()
    else:
        _render_review_page(platforms_config)


if __name__ == "__main__":
    main()
