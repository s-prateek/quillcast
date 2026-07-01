# Quillcast — Implementation Plan

Phases are sequential. Each phase ends with something that works end-to-end.

---

## Phase 1 — Foundation
*Goal: Project scaffold, config files, LinkedIn OAuth tokens stored locally.*

### 1.1 Project scaffold
- [x] `pyproject.toml` with dev dependencies (`pytest`, `ruff`)
- [x] Folder structure per `design.md`
- [x] `.env.example` documenting required environment variables
- [x] `.gitignore` catches `.env`, `data/`, `__pycache__/`

### 1.2 Config files
- [x] `config/platforms.yaml` (LinkedIn enabled, RSS feeds)
- [x] `config/topics.yaml` (voice + evergreen topics)

### 1.3 LinkedIn OAuth
- [ ] Register app at [LinkedIn Developer Portal](https://developer.linkedin.com/) — redirect URL `http://localhost:8080/callback`
- [ ] Request `w_member_social` scope
- [ ] Run: `python scripts/linkedin_oauth.py`
- [ ] Confirm tokens at `data/tokens/linkedin.json`

**Phase 1 done when:** Config files exist, OAuth tokens saved locally.

---

## Phase 2 — Content Generation
*Goal: Generate drafts via CLI (auto-pick topic) or explicit topic API.*

### 2.1 Shared models & storage
- [x] `shared/models.py` — `PostRecord`, `TopicCandidate`, `PublishResult`
- [x] `shared/drafts.py` — local JSON draft storage
- [x] `shared/config.py` — loads YAML from `config/`

### 2.2 RSS fetcher
- [x] `shared/rss.py` — fetch + parse RSS feeds with age filters

### 2.3 LLM calls
- [x] `shared/llm.py` — content generation (LLM call #2)
- [x] `shared/llm.py` — `curate_topic_candidates()` (LLM call #1)
- [x] `shared/discover.py` — RSS → curated topic list with LLM fallback

### 2.4 Generation orchestration
- [x] `shared/generate.py` — `generate_post_for_topic()` + CLI `generate_post()`
- [x] `scripts/run_generate_post.py` — CLI entrypoint (auto-pick)

**Phase 2 done when:** A draft JSON file exists in `data/drafts/`.

---

## Phase 3 — Publisher
*Goal: Publishing a draft posts the LinkedIn variant and updates the local record.*

- [x] `publishers/` — LinkedIn publisher + registry
- [x] `shared/publish.py` — shared publish/save/archive logic
- [x] `scripts/publish_post.py` — CLI publish

**Phase 3 done when:** A post goes live on LinkedIn and the draft shows `Status: POSTED`.

---

## Phase 4 — Streamlit UI
*Goal: Full workflow in the browser — discover, draft, review, publish.*

### 4.1 Discover + generate
- [x] `ui/components/discover.py` — fetch RSS, LLM-curate topics, pick + generate
- [x] `shared/discover.py` — topic discovery orchestration

### 4.2 Review + publish
- [x] `ui/components/platform_tab.py` — preview, edit, publish, archive
- [x] `ui/components/linkedin_preview.py` — LinkedIn card mock-up
- [x] `ui/app.py` — Discover + Review navigation

**Phase 4 done when:** You can open the UI, fetch topics, generate a draft, edit it, and publish to LinkedIn — no terminal required.

---

## Phase 5 — Open Source Prep
*Goal: A stranger can clone the repo and have Quillcast running.*

- [x] `README.md` with architecture and quick start
- [x] `docs/SETUP.md` local setup guide
- [x] `docs/design.md` — human-in-the-loop discover flow
- [x] `publishers/facebook.py` — stub with `NotImplementedError`
- [x] `publishers/blog/ghost.py` — stub with `NotImplementedError`
- [x] `CONTRIBUTING.md`
- [x] `.streamlit/config.toml` — headless by default (no auto-open browser)
- [x] CI installs runtime + dev dependencies
- [ ] Final check: no secrets in git history (run before first public release)

**Phase 5 done when:** Docs, stubs, and contributor guide are in place; repo is safe to share.

---

## Future Ideas

- Scheduled publishing (`ScheduledFor` field + local poller)
- Facebook / Ghost / WordPress publishers
- Post performance tracking
- Image generation for post visuals
