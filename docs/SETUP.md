# Quillcast — Setup Guide

Everything runs on your machine. No AWS account required.

---

## 1. Install

```bash
git clone https://github.com/s-prateek/quillcast.git
cd quillcast

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional, for tests/linting
```

---

## 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at least one LLM API key:

| Provider | Variables |
|----------|-----------|
| Claude (default) | `ANTHROPIC_API_KEY=sk-ant-...` |
| Gemini | `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=...` |

Get keys from:
- Claude: [console.anthropic.com](https://console.anthropic.com/)
- Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

---

## 3. Edit config files

### `config/topics.yaml`

Set your author voice and evergreen fallback topics:

```yaml
voice:
  author_name: Your Name
  description: Direct, opinionated, practical.
  target_audience: Software engineers and tech leads

evergreen_topics:
  - Lessons from shipping side projects
  - What I learned building in public
```

### `config/platforms.yaml`

Enable platforms and RSS feeds. LinkedIn and blog (Ghost) can run side by side:

```yaml
platforms:
  linkedin:
    enabled: true
    token_file: data/tokens/linkedin.json
  blog:
    enabled: true
    type: ghost
    default_status: draft
```

---

## 4. Generate your first draft

```bash
python scripts/run_generate_post.py
```

Expected output:

```json
{'post_id': '...', 'topic': '...', 'source_type': 'rss', 'platforms': ['linkedin']}
```

Check the draft file:

```bash
cat data/drafts/<post-id>.json
```

The file contains `ContentVariants` (LinkedIn text, etc.) and `OverallStatus: PENDING`.

---

## 5. LinkedIn OAuth (for publishing — Phase 3)

### Register a LinkedIn app

1. Go to [LinkedIn Developer Portal](https://developer.linkedin.com/)
2. Create an app and add redirect URL: `http://localhost:8080/callback`
3. Request the `w_member_social` scope (may require approval)

### Run OAuth

```bash
export LINKEDIN_CLIENT_ID=...
export LINKEDIN_CLIENT_SECRET=...
python scripts/linkedin_oauth.py
```

Tokens are saved to `data/tokens/linkedin.json` (gitignored). Verify:

```bash
ls -la data/tokens/linkedin.json
```

---

## 6b. Ghost blog

### Create a custom integration

**Local dev:** http://localhost:2368/ghost → **Settings → Integrations → Add custom integration**  
**Production:** `https://yourblog.com/ghost` → same path

Copy **API URL** and **Admin API key** (`id:secret`).

### Save credentials

Add to `.env` at the project root (see `.env.example`):

```bash
GHOST_URL=http://localhost:2368
GHOST_ADMIN_API_KEY=your_integration_id:your_integration_secret
```

Validate the connection:

```bash
pip install -r requirements.txt   # includes markdown
python scripts/ghost_setup.py
```

Optional: pass `--url` and `--key` to validate without editing `.env`.

### Publish a blog draft

Generate a draft with blog enabled (`blog.enabled: true` in `config/platforms.yaml`). Then:

```bash
python scripts/publish_post.py \
  --post-id <your-draft-uuid> \
  --platform blog \
  --dry-run
```

```bash
python scripts/publish_post.py \
  --post-id <your-draft-uuid> \
  --platform blog
```

Creates a **Ghost Admin draft** (`default_status: draft`). Open Ghost Admin → **Posts** to review and publish to the public site.

In Streamlit **Review → Blog** tab: edit title, markdown body, and tags, then **Publish**.

When moving to production, update `GHOST_URL` and `GHOST_ADMIN_API_KEY` in `.env` and re-run `python scripts/ghost_setup.py`.

---

## 7. Publish to LinkedIn (Phase 3)

### Prerequisites

1. LinkedIn app with `w_member_social` scope approved
2. OAuth tokens saved locally

```bash
python scripts/linkedin_oauth.py
ls data/tokens/linkedin.json
```

### Dry run (no post)

```bash
python scripts/publish_post.py \
  --post-id <your-draft-uuid> \
  --platform linkedin \
  --dry-run
```

### Publish for real

```bash
python scripts/publish_post.py \
  --post-id <your-draft-uuid> \
  --platform linkedin
```

On success the draft JSON updates to `Status: POSTED` with a `PlatformPostID`.

Optional: override text before posting:

```bash
python scripts/publish_post.py --post-id <uuid> --text "My edited post..."
```

---

## 8. Troubleshooting

### `ANTHROPIC_API_KEY is not set`

Copy `.env.example` to `.env` and add your key. Scripts load `.env` automatically from the project root.

```bash
cp .env.example .env
# Edit .env, then:
python scripts/run_generate_post.py
```

Or export manually:

```bash
set -a && source .env && set +a
python scripts/run_generate_post.py
```

### `No RSS articles and no evergreen topics configured`

Add topics to `config/topics.yaml` under `evergreen_topics`, or check that RSS feeds are reachable.

### `LLM API error 401`

Invalid API key. Regenerate at your provider's console.

### `LLM returned invalid JSON after retries`

The model returned malformed JSON. Try again, switch provider, or set `LLM_MODEL` to a more capable model.

### LinkedIn OAuth `redirect_uri mismatch`

Ensure `http://localhost:8080/callback` is registered exactly in your LinkedIn app settings.

---

## 9. Review UI

```bash
pip install -r ui/requirements.txt
streamlit run ui/app.py
```

Opens at http://localhost:8501 (browser auto-open disabled via `.streamlit/config.toml`).

### Discover

1. Open the **Discover** tab in the sidebar
2. Click **Fetch trending topics** — reads RSS feeds, then LLM curates ~8 post-worthy cards
3. Pick a topic and click **Generate draft for this topic**
4. You are taken to **Review** with the new draft open

### Review

- Sidebar lists `PENDING` drafts
  - Edit text, see LinkedIn preview, character counter
  - **Blog** tab: title, markdown body, tags, preview
  - **Publish** posts to LinkedIn or Ghost (blog drafts); **Archive** skips

Set `AUTHOR_NAME`, `AUTHOR_HEADLINE`, and optional `AUTHOR_PROFILE_PIC_URL` in `.env` for the preview card.

---

## 10. Directory layout after setup

```
quillcast/
├── config/           # your YAML config (committed)
├── data/             # generated locally (gitignored)
│   ├── drafts/       # one JSON file per draft
│   └── tokens/       # OAuth tokens per platform
└── .env              # API keys (gitignored)
```

---

## Next steps

See [CONTRIBUTING.md](../CONTRIBUTING.md) for dev setup, tests, and how to add a new platform publisher.
