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
*Goal: Running the script picks a topic, calls Claude/Gemini, and writes a local draft.*

### 2.1 Shared models & storage
- [x] `shared/models.py` — `PostRecord`, `PostContent`, `PublishResult`
- [x] `shared/drafts.py` — `put_record()`, `get_record()`, `list_records()`, `update_target_status()`
- [x] `shared/config.py` — loads YAML from `config/`

### 2.2 RSS fetcher
- [x] `shared/rss.py` — fetch + parse RSS feeds with age filters

### 2.3 LLM call
- [x] `shared/llm.py` — prompt builder + Claude/Gemini HTTP client
- [x] JSON parse with retry (max 2 attempts)

### 2.4 Generation orchestration
- [x] `shared/generate.py` — wire RSS → topic → LLM → save draft
- [x] `scripts/run_generate_post.py` — CLI entrypoint

**Phase 2 done when:** `python scripts/run_generate_post.py` creates a JSON draft in `data/drafts/`.

---

## Phase 3 — Publisher
*Goal: Publishing a draft posts the LinkedIn variant and updates the local record.*

### 3.1 Publisher abstraction
- [ ] `publishers/base.py` — `Publisher` ABC
- [ ] `publishers/registry.py` — platform name → Publisher class

### 3.2 LinkedIn publisher
- [ ] `publishers/linkedin.py`
  - [ ] Load tokens from `token_file` in `platforms.yaml`
  - [ ] Proactive token refresh if expiry within 7 days
  - [ ] `POST /rest/posts` with correct LinkedIn headers
  - [ ] Exponential backoff on 429
  - [ ] `render_preview()` for Streamlit

### 3.3 Publish script
- [ ] `scripts/publish_post.py` — load draft, call publisher, update `data/drafts/`

**Phase 3 done when:** A post goes live on LinkedIn and the draft shows `Status: POSTED`.

---

## Phase 4 — Review UI
*Goal: Streamlit app shows pending drafts, lets you edit, and publishes.*

### 4.1 Components
- [ ] `ui/components/linkedin_preview.py` — LinkedIn card HTML mock-up
- [ ] `ui/components/platform_tab.py` — preview + edit + publish/skip/archive

### 4.2 Streamlit app
- [ ] `ui/app.py` — sidebar draft list, platform tabs, publish flow
- [ ] `ui/requirements.txt` (`streamlit`)

**Phase 4 done when:** You can open the UI, edit a draft, hit Publish, and see it on LinkedIn.

---

## Phase 5 — Automation
*Goal: Daily generation without manual action.*

- [ ] Document cron setup (see `docs/SETUP.md`)
- [ ] Optional: `scripts/run_daily.sh` wrapper that sources `.env`
- [ ] Run for 3 days and verify 3 new drafts appear

**Phase 5 done when:** Drafts appear every morning without terminal commands.

---

## Phase 6 — Open Source Prep
*Goal: A stranger can clone the repo and have Quillcast running.*

- [x] `README.md` with architecture and quick start
- [x] `docs/SETUP.md` local setup guide
- [ ] `publishers/facebook.py` — stub with `NotImplementedError`
- [ ] `CONTRIBUTING.md`
- [ ] Final check: no secrets in git history

---

## Future Ideas

- Scheduled publishing (`ScheduledFor` field + local poller)
- Facebook / Ghost / WordPress publishers
- Post performance tracking
- Image generation for post visuals
