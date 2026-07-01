from __future__ import annotations

import json
import os
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from publishers.registry import get
from shared.publish import archive_target, publish_draft, save_edited_content
from shared.models import PostRecord
from ui.components.linkedin_preview import render_linkedin_preview


def _char_counter_style(length: int, limit: int) -> str:
    if length > limit:
        return "color: #d32f2f; font-weight: 600;"
    if length > int(limit * 0.85):
        return "color: #ed6c02; font-weight: 600;"
    return "color: #2e7d32; font-weight: 600;"


def _variant_text(record: PostRecord, platform: str) -> str:
    target = record.Targets.get(platform)
    if target and target.EditedContent:
        return target.EditedContent

    variant = record.ContentVariants.get(platform)
    if isinstance(variant, str):
        return variant
    if isinstance(variant, dict):
        return json.dumps(variant, indent=2)
    return ""


def _render_preview(platform: str, text: str, profile: dict, platform_config: dict) -> None:
    if platform == "linkedin":
        html = render_linkedin_preview(text, profile)
    else:
        publisher = get(platform, platform_config=platform_config)
        html = publisher.render_preview(text, profile)
    components.html(html, height=280, scrolling=False)


def render_platform_tab(
    record: PostRecord,
    platform: str,
    *,
    platform_config: dict[str, Any],
    profile: dict[str, str],
) -> None:
    target = record.Targets.get(platform)
    if target is None:
        st.warning(f"No target for platform {platform!r}.")
        return

    publisher = get(platform, platform_config=platform_config)
    constraints = publisher.get_constraints()
    char_limit = int(constraints.get("char_limit", 3000))

    if target.Status == "POSTED":
        st.success(f"Published · ID: {target.PlatformPostID or 'unknown'}")
        if target.PublishedAt:
            st.caption(f"Published at {target.PublishedAt}")
        st.text_area("Posted content", value=_variant_text(record, platform), disabled=True, height=240)
        return

    if target.Status == "ARCHIVED":
        st.info("Archived — skipped for this platform.")
        return

    if target.Status == "FAILED" and target.ErrorLog:
        st.error(target.ErrorLog)

    default_text = _variant_text(record, platform)
    editor_key = f"editor-{record.PostID}-{platform}"
    text = st.text_area(
        "Edit draft",
        value=default_text,
        height=280,
        key=editor_key,
        label_visibility="collapsed",
    )

    st.markdown(
        f'<p style="{_char_counter_style(len(text), char_limit)}">{len(text)} / {char_limit} characters</p>',
        unsafe_allow_html=True,
    )

    st.subheader("Preview")
    _render_preview(platform, text, profile, platform_config)

    col_save, col_publish, col_skip = st.columns(3)

    with col_save:
        if st.button("Save edits", key=f"save-{record.PostID}-{platform}", use_container_width=True):
            save_edited_content(post_id=record.PostID, platform=platform, text=text)
            st.toast("Draft saved.")
            st.rerun()

    with col_publish:
        if st.button("Publish", key=f"publish-{record.PostID}-{platform}", type="primary", use_container_width=True):
            if len(text) > char_limit:
                st.error(f"Post is too long ({len(text)}/{char_limit} chars).")
            else:
                try:
                    result = publish_draft(
                        post_id=record.PostID,
                        platform=platform,
                        text=text,
                    )
                    st.success(f"Published! Post ID: {result['platform_post_id']}")
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

    with col_skip:
        if st.button("Archive", key=f"archive-{record.PostID}-{platform}", use_container_width=True):
            archive_target(post_id=record.PostID, platform=platform)
            st.toast("Archived.")
            st.rerun()

    if not publisher.validate_credentials():
        st.warning(
            f"Credentials missing or invalid for {platform}. "
            f"Run `python scripts/linkedin_oauth.py` if needed."
        )
