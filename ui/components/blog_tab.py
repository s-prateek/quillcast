from __future__ import annotations

from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from publishers.blog.ghost import GhostPublisher, ghost_admin_edit_url
from publishers.registry import get
from shared.blog_content import blog_content_from_variant, serialize_blog_content
from shared.models import PostRecord
from shared.publish import archive_target, publish_draft, save_edited_content


def _load_fields(record: PostRecord) -> dict[str, Any]:
    target = record.Targets.get("blog")
    if target and target.EditedContent:
        parsed = blog_content_from_variant(target.EditedContent)
        if parsed:
            return parsed

    parsed = blog_content_from_variant(record.ContentVariants.get("blog"))
    if parsed:
        return parsed

    return {"title": record.Topic, "body": "", "tags": []}


def render_blog_tab(
    record: PostRecord,
    *,
    platform_config: dict[str, Any],
    profile: dict[str, str],
) -> None:
    target = record.Targets.get("blog")
    if target is None:
        st.warning("No blog target for this draft.")
        return

    publisher = get("blog", platform_config=platform_config)
    constraints = publisher.get_constraints()
    char_limit = int(constraints.get("char_limit", 100_000))

    if target.Status == "POSTED":
        st.success(f"Sent to Ghost · post id: {target.PlatformPostID or 'unknown'}")
        if target.PublishedAt:
            st.caption(f"Sent at {target.PublishedAt}")
        if target.PlatformPostID:
            try:
                config = GhostPublisher(platform_config=platform_config)._config()
                edit_url = ghost_admin_edit_url(config["url"], target.PlatformPostID)
                st.markdown(f"[Open in Ghost Admin]({edit_url})")
            except RuntimeError:
                pass
        fields = _load_fields(record)
        st.text_input("Title", value=fields["title"], disabled=True)
        st.text_area("Body", value=fields["body"], disabled=True, height=280)
        return

    if target.Status == "ARCHIVED":
        st.info("Archived — skipped for blog.")
        return

    if target.Status == "FAILED" and target.ErrorLog:
        st.error(target.ErrorLog)

    fields = _load_fields(record)
    title = st.text_input("Title", value=fields["title"], key=f"blog-title-{record.PostID}")
    body = st.text_area(
        "Body (markdown)",
        value=fields["body"],
        height=360,
        key=f"blog-body-{record.PostID}",
        label_visibility="collapsed",
    )
    tags_raw = st.text_input(
        "Tags (comma-separated)",
        value=", ".join(fields.get("tags") or []),
        key=f"blog-tags-{record.PostID}",
        help="Ghost tags, e.g. AI, Dev Tools, Spec-Driven Workflows",
    )
    tags = [part.strip() for part in tags_raw.split(",") if part.strip()]
    serialized = serialize_blog_content(title=title, body=body, tags=tags)

    st.markdown(
        f'<p style="color:#64748b;">Body length: {len(body)} / {char_limit} characters</p>',
        unsafe_allow_html=True,
    )

    st.subheader("Preview")
    preview_profile = {**profile, "site_name": profile.get("name", "Your Blog")}
    html = publisher.render_preview(serialized, preview_profile)
    components.html(html, height=420, scrolling=True)

    col_save, col_publish, col_skip = st.columns(3)

    with col_save:
        if st.button("Save edits", key=f"save-{record.PostID}-blog", use_container_width=True):
            save_edited_content(post_id=record.PostID, platform="blog", text=serialized)
            st.toast("Blog draft saved.")
            st.rerun()

    with col_publish:
        if st.button("Publish", key=f"publish-{record.PostID}-blog", type="primary", use_container_width=True):
            if not title.strip():
                st.error("Title is required.")
            elif not body.strip():
                st.error("Body is required.")
            elif len(body) > char_limit:
                st.error(f"Body is too long ({len(body)}/{char_limit} chars).")
            else:
                try:
                    result = publish_draft(
                        post_id=record.PostID,
                        platform="blog",
                        text=serialized,
                    )
                    post_id = result.get("platform_post_id", "")
                    st.success(f"Created Ghost draft! Post id: {post_id}")
                    try:
                        config = GhostPublisher(platform_config=platform_config)._config()
                        st.markdown(f"[Open in Ghost Admin]({ghost_admin_edit_url(config['url'], post_id)})")
                    except RuntimeError:
                        pass
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

    with col_skip:
        if st.button("Archive", key=f"archive-{record.PostID}-blog", use_container_width=True):
            archive_target(post_id=record.PostID, platform="blog")
            st.toast("Archived.")
            st.rerun()

    if not publisher.validate_credentials():
        st.warning(
            "Ghost credentials missing or invalid. "
            "Set `GHOST_URL` and `GHOST_ADMIN_API_KEY` in `.env` (see `.env.example`). "
            "Validate with `python scripts/ghost_setup.py`."
        )
