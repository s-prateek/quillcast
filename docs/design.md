# Design Document: Quillcast

> **Status:** In design.

---

## 1. Overview & Goals

A serverless, event-driven application that:

- Discovers trending topics daily via RSS feeds and a curated manual list
- Generates platform-adapted draft posts using Amazon Bedrock (Claude Haiku)
- Notifies you via Telegram when drafts are ready for review
- Provides a **local** Streamlit UI for previewing (platform-accurate card mock-up), editing, and approving posts
- Publishes approved content to LinkedIn (and future platforms) via their APIs

**Design Priorities (in order):**

1. **Cost** — Target ~$0/month AWS bill. All services must be free-tier eligible at personal-use volume.
2. **Low Maintenance** — Config-driven. Adding a topic or a new platform should require no code changes.
3. **Extensibility** — Clean publisher abstraction. New platforms = one new file.
4. **Open Source Friendly** — AWS CDK for reproducible infra, local-first UI, no hardcoded credentials anywhere.

---

## 2. Architecture

### High-Level Flow

```
EventBridge Scheduler (daily cron)
        │
        ▼
generate_post Lambda
  ├── Fetch & score articles from RSS feeds
  ├── Merge with topics.yaml overrides (from S3)
  ├── Select best topic for the day
  ├── Invoke Bedrock (Claude Haiku) → structured JSON with a variant per enabled platform
  ├── Write PostRecord to DynamoDB (OverallStatus: PENDING)
  └── Send Telegram notification: "📝 New draft ready for review"

User opens Streamlit UI locally  →  streamlit run ui/app.py
  ├── Queries DynamoDB GSI for PENDING records
  ├── Shows per-draft view with a tab per enabled platform
  ├── Each tab: platform-accurate post preview + editable text area + char counter
  └── On "Publish" → calls publish_post Lambda via Function URL (secrets stay server-side)

publish_post Lambda
  ├── Reads PostRecord from DynamoDB
  ├── Loads OAuth tokens from SSM Parameter Store
  ├── Selects the correct Publisher class for the platform
  ├── Calls platform API with retry + exponential backoff
  └── Updates DynamoDB: Target.Status → POSTED, stores PlatformPostID and PublishedAt
```

### AWS Services & Cost

| Service | Purpose | Cost at Personal Scale |
|---|---|---|
| EventBridge Scheduler | Daily cron trigger | Free |
| Lambda (×2) | `generate_post`, `publish_post` | Free (1M invocations/month free tier) |
| DynamoDB On-Demand | Post records + history | Free (25 GB + 25 WCU/RCU free tier) |
| Bedrock — Claude Haiku | LLM generation | ~$0.01/month (30 posts × ~500 tokens) |
| S3 | `platforms.yaml`, `topics.yaml`, RSS cache | ~$0 |
| SSM Parameter Store (Standard) | OAuth tokens per platform | Free |
| Telegram Bot API | Push notifications | Free |
| **Total** | | **~$0.01–0.05/month** |

> No App Runner, no Fargate, no Secrets Manager. The Streamlit UI runs locally on demand — it is not hosted.

---

## 3. Data Model

### DynamoDB Table: `quillcast-drafts`

**Primary Key:** `PostID` (String, UUIDv4)

**GSI — `OverallStatus-CreatedAt-index`**
- Partition key: `OverallStatus` (`PENDING` | `COMPLETE`)
- Sort key: `CreatedAt`
- Purpose: lets the Streamlit UI fetch all pending drafts in one query, no full table scan.

**Record Schema:**

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

**OverallStatus logic (maintained by Lambda on every update):**
- `PENDING` — at least one Target has `DRAFT` status
- `COMPLETE` — all Targets are `POSTED`, `FAILED`, or `ARCHIVED`

`ContentVariants` only contains keys for currently enabled platforms. Enabling a new platform later adds future records but does not backfill old ones.

---

## 4. Topic Discovery

Two complementary sources merged before each generation run.

### A. RSS Feeds (Primary — auto-discovers trends)

Configured in `config/platforms.yaml`. Lambda fetches, parses, and filters articles by age and relevance score.

```yaml
rss_feeds:
  - url: https://hnrss.org/frontpage
    category: tech
  - url: https://feeds.feedburner.com/TechCrunch
    category: tech
  - url: https://www.theverge.com/rss/index.xml
    category: tech

rss_filter:
  min_article_age_hours: 1
  max_article_age_hours: 48
  max_articles_per_run: 5
```

Lambda uses a lightweight Bedrock call (or simple keyword heuristic) to pick the most relevant article from the fetched batch.

### B. `topics.yaml` in S3 (Fallback & Evergreen Override)

Used when RSS yields nothing relevant, or for timeless personal topics. Edit in S3 — no deployment needed.

```yaml
voice:
  description: "Direct, opinionated, practical. No fluff."
  target_audience: "Software engineers and tech leads"
  author_name: "Your Name"

evergreen_topics:
  - "Lessons from shipping side projects"
  - "What nobody tells you about distributed systems"
  - "My honest take on [recent trend]"
```

If both sources have candidates, RSS takes priority. `topics.yaml` is always appended to the Bedrock prompt as author context regardless of which source wins.

---

## 5. Content Generation (`generate_post` Lambda)

**One Bedrock call per daily run** requesting structured JSON output with all platform variants. Single call keeps costs minimal and keeps variants thematically consistent.

Prompt structure:

```
System: You are a ghostwriter for {author_name}. Voice: {voice_description}.
        Target audience: {target_audience}.

User:   Topic: {selected_topic}
        Source: {source_url}

        Generate social content as valid JSON for these platforms: {enabled_platforms}

        {
          "linkedin": "...",       // max 3000 chars, professional, 3 paragraphs, ends with a question or CTA
          "facebook": "...",       // max 500 chars, casual, conversational
          "blog": {
            "title": "...",
            "body": "...",         // full markdown, 600–1200 words
            "tags": ["tag1"]
          }
        }

        Only include keys for: {enabled_platforms}
```

On success: write record to DynamoDB, then send Telegram notification.
On failure: write to CloudWatch Logs, send Telegram error alert. EventBridge DLQ captures the failed invocation for manual retry.

---

## 6. Review UI (Streamlit — Local Only)

```
streamlit run ui/app.py
```

The UI is **never deployed**. It runs on your laptop when you open it to review drafts.

### Layout

```
┌──────────────────────────────────────────────────────┐
│  📋  ContentPilot — 2 drafts pending                 │
│  ──────────────────────────────────────────────────  │
│  Sidebar                    │  Main panel            │
│  ─────────────              │  ───────────────────── │
│  ▶ AI agents · Jun 28       │  Topic: AI agents...   │
│    LinkedIn ✏️  Blog ─      │  Source: TechCrunch    │
│  ─ SRE lessons · Jun 27     │                        │
│    LinkedIn ✅              │  [ LinkedIn ] [ Blog ] │
│                             │                        │
│                             │  ┌─ LinkedIn Preview ─┐│
│                             │  │ 👤 Name · 1st      ││
│                             │  │    Software Eng.   ││
│                             │  │                    ││
│                             │  │  The enterprise... ││
│                             │  │  ...see more       ││
│                             │  │ 👍 💬 🔁           ││
│                             │  └────────────────────┘│
│                             │                        │
│                             │  ✏️ Edit               │
│                             │  ┌──────────────────┐  │
│                             │  │ The enterprise.. │  │
│                             │  └──────────────────┘  │
│                             │  847 / 3000  ✅        │
│                             │                        │
│                             │  [✅ Publish] [⏭ Skip] │
│                             │  [🗓 Schedule] [🗑]    │
└──────────────────────────────────────────────────────┘
```

### Platform Preview Components

Each `Publisher` class implements a `render_preview(text, profile_config) -> str` method returning HTML. Streamlit injects this via `st.components.v1.html()`. The UI has zero platform-specific logic — adding a new platform's preview is done entirely inside its Publisher file.

Platform constraints (character limits, image support, etc.) are also sourced from `publisher.get_constraints()` and displayed in the UI dynamically.

### Publish Action

"Publish" calls the `publish_post` Lambda via its **Function URL** (HTTPS, IAM-authenticated). The Streamlit app never holds OAuth tokens — they live exclusively in SSM, accessed only by the Lambda.

---

## 7. Telegram Notifications

Telegram is used for **push notifications only** — not for approval or editing.

| Event | Telegram Message |
|---|---|
| Draft ready | "📝 New draft ready: *AI agents in enterprise*. Open review UI to approve." |
| Post published | "✅ Posted to LinkedIn: [link]" |
| Generation failed | "❌ Generation failed: {error summary}. Check CloudWatch." |

Setup: create a bot via @BotFather → store `bot_token` and `chat_id` in SSM at `/quillcast/telegram/bot_token` and `/quillcast/telegram/chat_id`.

---

## 8. Publisher System

### Interface (`publishers/base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class PostContent:
    text: str
    platform: str
    media_urls: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # blog title/tags, etc.

@dataclass
class PublishResult:
    success: bool
    platform_post_id: str | None = None
    error: str | None = None

class Publisher(ABC):
    @abstractmethod
    def publish(self, content: PostContent) -> PublishResult: ...

    @abstractmethod
    def validate_credentials(self) -> bool: ...

    @abstractmethod
    def get_constraints(self) -> dict: ...
    # e.g. {"char_limit": 3000, "supports_images": True, "supports_links": True}

    @abstractmethod
    def render_preview(self, text: str, profile: dict) -> str: ...
    # Returns HTML injected into Streamlit via st.components.v1.html()
```

### Platform Registry

Publishers are discovered at runtime from `config/platforms.yaml`. The Lambda dispatcher does:

```python
publisher = PublisherRegistry.get(platform)  # returns the right Publisher subclass
result = publisher.publish(content)
```

### Adding a New Platform (zero core changes)

1. Create `publishers/<platform>.py` implementing `Publisher`
2. Set `enabled: true` in `config/platforms.yaml`
3. Store credentials in SSM
4. Done — the UI tab appears automatically on next `streamlit run`

---

## 9. Platform Configuration (`config/platforms.yaml`)

```yaml
platforms:
  linkedin:
    enabled: true
    ssm_token_key: /quillcast/linkedin/tokens   # stores access_token, refresh_token, token_expiry

  facebook:
    enabled: false      # ← flip this when ready, no code changes needed
    ssm_token_key: /quillcast/facebook/tokens

  blog:
    enabled: false
    type: ghost         # ghost | wordpress | hugo_github
    ssm_token_key: /quillcast/blog/tokens
```

---

## 10. LinkedIn API Integration

- **Auth:** OAuth 2.0 three-legged flow. Store `access_token`, `refresh_token`, and `token_expiry` (ISO 8601) together as a JSON string in a single SSM Standard Parameter.
- **Token Refresh:** Before every publish call, check `token_expiry`. If within 7 days, refresh proactively and update SSM. LinkedIn access tokens expire in 60 days; refresh tokens in 365 days.
- **Endpoint:** `POST /rest/posts`
- **Required Headers:**
  - `X-Restli-Protocol-Version: 2.0.0`
  - `LinkedIn-Version: 202606` (update to latest stable each year)
  - `Authorization: Bearer {access_token}`
- **Rate Limiting:** Exponential backoff on `429` responses — max 3 retries, base delay 2s, jitter added.
- **Required Permission:** `w_member_social` (request during Developer App registration)

---

## 11. Infrastructure (AWS CDK — Python)

Three stacks, deployed together via `cdk deploy --all`:

| Stack | Resources |
|---|---|
| `StorageStack` | DynamoDB table + GSI; S3 bucket for config files |
| `LambdaStack` | `generate_post` Lambda; `publish_post` Lambda + Function URL; IAM roles |
| `SchedulerStack` | EventBridge Scheduler daily cron; Lambda invoke permission; DLQ for failed invocations |

**IAM — least privilege:**

| Lambda | Permissions |
|---|---|
| `generate_post` | `bedrock:InvokeModel`, `dynamodb:PutItem`, `s3:GetObject` (config bucket), `ssm:GetParameter` (Telegram only) |
| `publish_post` | `dynamodb:GetItem`, `dynamodb:UpdateItem`, `ssm:GetParameter` (platform tokens), `ssm:PutParameter` (token refresh) |

---

## 12. Project Structure

```
quillcast/
├── cdk/
│   ├── app.py
│   └── stacks/
│       ├── storage_stack.py
│       ├── lambda_stack.py
│       └── scheduler_stack.py
│
├── lambdas/
│   ├── generate_post/
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── publish_post/
│       ├── handler.py
│       └── requirements.txt
│
├── publishers/
│   ├── base.py              # Abstract Publisher interface
│   ├── registry.py          # Maps platform name → Publisher class
│   ├── linkedin.py
│   ├── facebook.py          # Stub — enable via platforms.yaml
│   └── blog/
│       ├── ghost.py         # Stub
│       └── wordpress.py     # Stub
│
├── ui/
│   ├── app.py               # Streamlit entrypoint
│   ├── components/
│   │   └── platform_tab.py  # Renders preview + edit + publish per platform
│   └── requirements.txt
│
├── shared/
│   ├── models.py            # PostContent, PublishResult, PostRecord dataclasses
│   ├── dynamodb.py          # DynamoDB read/write helpers
│   └── config.py            # Loads platforms.yaml + topics.yaml from S3
│
├── config/
│   ├── platforms.yaml       # Platform enable/disable + SSM keys
│   └── topics.yaml          # Author voice + evergreen topics
│
├── tests/
├── .env.example             # Documents all required env vars, no real values
├── pyproject.toml
└── README.md
```

---

## 13. Implementation Phases

| Phase | Tasks |
|---|---|
| **1 — Foundation** | Finalize project name; CDK `StorageStack` (DynamoDB + S3); upload `platforms.yaml` + `topics.yaml` to S3; LinkedIn Developer App registration + OAuth flow; store tokens in SSM |
| **2 — Generation** | `shared/models.py` dataclasses; `shared/config.py` S3 loader; `generate_post` Lambda (RSS fetch → topic selection → Bedrock call → DynamoDB write → Telegram notify); CDK `LambdaStack` |
| **3 — Publisher** | `publishers/base.py` interface + `registry.py`; `publishers/linkedin.py` with OAuth refresh + retry; `publish_post` Lambda + Function URL |
| **4 — UI** | Streamlit app: sidebar draft list, platform tabs, LinkedIn preview component, edit + char counter + publish flow |
| **5 — Automation** | CDK `SchedulerStack` (EventBridge daily cron + DLQ); end-to-end test run; AWS Budget alert at $5/month |
| **6 — Open Source Prep** | README setup guide; `.env.example`; stub publishers for Facebook + blog; `CONTRIBUTING.md` |

---

## 14. Risks & Mitigation

| Risk | Mitigation |
|---|---|
| LinkedIn API changes | All API logic isolated in `publishers/linkedin.py`. Core Lambda never touches LinkedIn directly. |
| OAuth token expiry | Proactive refresh 7 days before expiry. `token_expiry` stored in SSM alongside token. |
| RSS noise / off-topic content | Age filters + relevance scoring in `generate_post`. Manual `topics.yaml` always available as override. |
| Hallucinations / generic posts | Human-in-the-loop is mandatory. No post goes out without UI preview and explicit approval. |
| Runaway Lambda costs | AWS Budget alert at $5/month. DLQ on EventBridge → Lambda captures failures without infinite retry loops. |
| Open-source credential leaks | `.env.example` with no real values; all secrets in SSM; no hardcoded credentials anywhere in codebase. |

---

## 15. Open Questions

- [ ] **Blog platform** — Ghost, WordPress, or Hugo + GitHub Pages? Affects Phase 6 stub implementation
- [ ] **Author profile config** — name, headline, profile picture URL needed for the Streamlit LinkedIn preview mock-up (not sent to LinkedIn, display only)
- [ ] **Scheduling** — the UI includes a "Schedule" button and LinkedIn supports `scheduledPublishTime`. Include in Phase 3 or defer to later?