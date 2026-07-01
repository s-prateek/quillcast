from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.config import enabled_platforms, load_platforms_config, load_topics_config  # noqa: E402
from shared.drafts import get_record, list_records  # noqa: E402
from shared.env import load_project_env  # noqa: E402
from ui.components.discover import render_discover_page  # noqa: E402
from ui.components.platform_tab import render_platform_tab  # noqa: E402

load_project_env()

st.set_page_config(page_title="Quillcast", page_icon="🪶", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "Discover"
if "selected_draft_id" not in st.session_state:
    st.session_state.selected_draft_id = None


def _author_profile() -> dict[str, str]:
    topics = load_topics_config()
    voice = topics.get("voice", {})
    return {
        "name": os.environ.get("AUTHOR_NAME") or voice.get("author_name", "Your Name"),
        "headline": os.environ.get("AUTHOR_HEADLINE", "Your Headline"),
        "profile_pic_url": os.environ.get("AUTHOR_PROFILE_PIC_URL", ""),
    }


def _pending_drafts():
    return list_records(status="PENDING")


def _draft_label(record) -> str:
    topic = record.Topic[:48] + ("…" if len(record.Topic) > 48 else "")
    date = record.CreatedAt[:10]
    return f"{topic} · {date}"


def _render_review_page(platforms_config: dict, enabled: list[str]) -> None:
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

    record = get_record(selected_id)
    if record is None:
        st.error("Draft not found.")
        return

    st.subheader(record.Topic)
    meta_cols = st.columns(2)
    with meta_cols[0]:
        st.caption(f"Created {record.CreatedAt}")
    with meta_cols[1]:
        if record.SourceURL:
            st.caption(f"Source: [{record.SourceType}]({record.SourceURL})")
        else:
            st.caption(f"Source: {record.SourceType}")

    profile = _author_profile()
    tab_platforms = [p for p in enabled if p in record.Targets]
    if not tab_platforms:
        st.warning("This draft has no platform targets.")
        return

    tabs = st.tabs([p.capitalize() for p in tab_platforms])
    for platform, tab in zip(tab_platforms, tabs):
        with tab:
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
    enabled = enabled_platforms(platforms_config)

    with st.sidebar:
        st.session_state.page = st.radio(
            "Navigate",
            options=["Discover", "Review"],
            index=0 if st.session_state.page == "Discover" else 1,
            label_visibility="collapsed",
        )

    if st.session_state.page == "Discover":
        render_discover_page()
    else:
        _render_review_page(platforms_config, enabled)


if __name__ == "__main__":
    main()
