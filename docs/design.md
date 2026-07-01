# Design Document: Quillcast

> **Status:** Local-first architecture. No AWS dependencies.

---

## 1. Overview & Goals

A local content pipeline that:

- Discovers trending topics daily via RSS feeds and a curated manual list
- Generates platform-adapted draft posts using **Claude or Gemini** (direct API)
- Surfaces pending drafts in a **local** Streamlit UI for previewing, editing, and approving posts
- Publishes approved content to LinkedIn (and future platforms) via their APIs

**Design Priorities (in order):**

1. **Simplicity** — Runs on your laptop. No cloud account required for core workflow.
2. **Low Maintenance** — Config-driven. Adding a topic or platform requires no code changes.
3. **Extensibility** — Clean publisher abstraction. New platforms = one new file.
4. **Open Source Friendly** — Local-first, no hardcoded credentials, secrets in `.env` and `data/tokens/`.

---

## 2. Architecture

### High-Level Flow

```
You run scripts/run_generate_post.py  (or cron)
        │
        ▼
shared/generate.py
  ├── Fetch articles from RSS feeds (shared/rss.py)
  ├── Load config/topics.yaml + config/platforms.yaml
  ├── Select best topic for the run
  ├── Call Claude or Gemini API (shared/llm.py) → structured JSON per platform
  └── Write PostRecord to data/drafts/<post-id>.json (OverallStatus: PENDING)

User opens Streamlit UI locally  →  streamlit run ui/app.py
  ├── Reads PENDING drafts from data/drafts/
  ├── Shows per-draft view with a tab per enabled platform
  ├── Each tab: platform preview + editable text area + char counter
  └── On "Publish" → calls publishers/linkedin.py directly

publishers/linkedin.py
  ├── Loads OAuth tokens from data/tokens/linkedin.json
  ├── Calls LinkedIn REST API with retry + exponential backoff
  └── Updates draft JSON: Target.Status → POSTED, stores PlatformPostID
```

### Cost at Personal Scale

| Item | Cost |
|------|------|
| Claude Haiku or Gemini Flash | ~$0.01–0.50/month (≈30 posts) |
| LinkedIn API | Free |
| Cloud infrastructure | **$0** |

---

## 3. Data Model

### Local Draft Files: `data/drafts/<post-id>.json`

One JSON file per draft. Same schema as the original DynamoDB design:

```json
{
  "PostID": "550e8400-e29b-41d4-a716-446655440000",
  "CreatedAt": "2026-06-28T08:00:00Z",
  "UpdatedAt": "2026-06-28T09:15:00Z",
  "Topic": "AI agents in enterprise 2026",
  "SourceURL": "https://example.com/article",
  "SourceType": "rss",
  "OverallStatus": "PENDING",
  "ContentVariants": {
    "linkedin": "Three sharp paragraphs, professional tone...",
    "facebook": "Same idea, casual and conversational...",
    "blog": {
      "title": "...",
      "body": "Full markdown article...",
      "tags": ["ai", "engineering"]
    }
  },
  "Targets": {
    "linkedin": {
      "Status": "DRAFT",
      "EditedContent": null,
      "PlatformPostID": null,
      "PublishedAt": null,
      "ErrorLog": null,
      "RetryCount": 0
    }
  }
}
```

**Target Status lifecycle:** `DRAFT` → `POSTED` | `FAILED` | `ARCHIVED`

**OverallStatus logic:**
- `PENDING` — at least one Target has `DRAFT` status
- `COMPLETE` — all Targets are `POSTED`, `FAILED`, or `ARCHIVED`

### OAuth Tokens: `data/tokens/<platform>.json`

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_expiry": "2026-08-28T12:00:00+00:00"
}
```

Gitignored. Never committed.

---

## 4. Topic Discovery

### A. RSS Feeds (Primary)

Configured in `config/platforms.yaml`. Fetched and filtered by age window.

```yaml
rss_feeds:
  - url: https://hnrss.org/frontpage
    category: tech

rss_filter:
  min_article_age_hours: 1
  max_article_age_hours: 48
  max_articles_per_run: 5
```

Newest matching article wins.

### B. Evergreen Topics (Fallback)

From `config/topics.yaml`. Used when RSS yields nothing.

```yaml
voice:
  description: "Direct, opinionated, practical."
  target_audience: "Software engineers and tech leads"
  author_name: "Your Name"

evergreen_topics:
  - "Lessons from shipping side projects"
```

`topics.yaml` voice is always included in the LLM prompt regardless of topic source.

---

## 5. Content Generation

**One LLM API call per run** requesting structured JSON with all platform variants.

Prompt structure (see `shared/llm.py`):

```
System: You are a ghostwriter for {author_name}. Voice: {voice_description}.
        Target audience: {target_audience}.

User:   Topic: {selected_topic}
        Source: {source_url}

        Generate social content as valid JSON for these platforms: {enabled_platforms}
        ...
```

Provider selection via `LLM_PROVIDER` env var (`claude` or `gemini`).

On success: write `data/drafts/<post-id>.json`.  
On failure: raise exception; caller logs to stderr.

---

## 6. Review UI (Streamlit — Local Only)

```
streamlit run ui/app.py
```

Never deployed. Runs on your laptop when you want to review drafts.

### Publish Action

"Publish" calls `publishers/linkedin.py` directly from the UI process. OAuth tokens are read from `data/tokens/linkedin.json` at publish time.

---

## 7. Publisher System

### Interface (`publishers/base.py` — planned)

```python
class Publisher(ABC):
    @abstractmethod
    def publish(self, content: PostContent) -> PublishResult: ...

    @abstractmethod
    def validate_credentials(self) -> bool: ...

    @abstractmethod
    def get_constraints(self) -> dict: ...

    @abstractmethod
    def render_preview(self, text: str, profile: dict) -> str: ...
```

### Adding a New Platform

1. Create `publishers/<platform>.py` implementing `Publisher`
2. Set `enabled: true` in `config/platforms.yaml` with a `token_file`
3. Store OAuth tokens at that path
4. UI tab appears automatically

---

## 8. Platform Configuration

```yaml
platforms:
  linkedin:
    enabled: true
    token_file: data/tokens/linkedin.json

  facebook:
    enabled: false
    token_file: data/tokens/facebook.json

  blog:
    enabled: false
    type: ghost
    token_file: data/tokens/blog.json
```

---

## 9. LinkedIn API Integration

- **Auth:** OAuth 2.0 via `scripts/linkedin_oauth.py` → saves to `data/tokens/linkedin.json`
- **Token Refresh:** Before publish, refresh if expiry within 7 days; update token file
- **Endpoint:** `POST /rest/posts`
- **Required Permission:** `w_member_social`

---

## 10. Project Structure

```
quillcast/
├── shared/
│   ├── generate.py          # Orchestration: RSS → LLM → save
│   ├── llm.py               # Claude / Gemini client
│   ├── rss.py               # RSS fetcher
│   ├── drafts.py            # Local JSON storage
│   ├── config.py            # YAML loader
│   └── models.py            # Dataclasses
│
├── publishers/              # Platform integrations
├── ui/                      # Streamlit app
│
├── config/
│   ├── platforms.yaml
│   └── topics.yaml
│
├── data/                    # gitignored
│   ├── drafts/
│   └── tokens/
│
├── scripts/
│   ├── run_generate_post.py
│   └── linkedin_oauth.py
│
├── docs/
├── tests/
├── .env.example
└── requirements.txt
```

---

## 11. Implementation Phases

See [PLAN.md](PLAN.md).

| Phase | Focus |
|-------|-------|
| 1 | Config + LinkedIn OAuth |
| 2 | Content generation (done) |
| 3 | LinkedIn publisher |
| 4 | Streamlit UI |
| 5 | Cron automation |
| 6 | Open source polish |

---

## 12. Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| LinkedIn API changes | Isolated in `publishers/linkedin.py` |
| OAuth token expiry | Proactive refresh; expiry stored in token file |
| RSS noise | Age filters + evergreen fallback |
| Hallucinations | Human-in-the-loop mandatory |
| Credential leaks | `.env` and `data/` gitignored; no secrets in code |
| LLM API costs | Pay-as-you-go; ~pennies per month at personal volume |

---

## 13. Open Questions

- [ ] **Blog platform** — Ghost, WordPress, or Hugo + GitHub Pages?
- [ ] **Scheduling** — local poller vs LinkedIn native `scheduledPublishTime`?
