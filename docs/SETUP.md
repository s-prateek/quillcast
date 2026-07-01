# Quillcast — Setup Guide

Everything runs on your machine. No AWS account required.

---

## 1. Install

```bash
git clone https://github.com/your-username/quillcast.git
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

Enable platforms and RSS feeds. LinkedIn is enabled by default:

```yaml
platforms:
  linkedin:
    enabled: true
    token_file: data/tokens/linkedin.json
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

## 6. Publish to LinkedIn (Phase 3)

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

## 7. Troubleshooting

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

## 8. Review UI (Phase 4)

Open the Streamlit app to preview, edit, and publish pending drafts:

```bash
pip install -r ui/requirements.txt
streamlit run ui/app.py
```

- **Sidebar** — lists `PENDING` drafts from `data/drafts/`
- **Main panel** — topic, source link, platform tabs
- **LinkedIn tab** — card preview, editable text, character counter
- **Publish** — posts to LinkedIn and updates the draft JSON
- **Archive** — skip a platform without publishing

Set `AUTHOR_NAME`, `AUTHOR_HEADLINE`, and optional `AUTHOR_PROFILE_PIC_URL` in `.env` for the LinkedIn preview card.

---

## 9. Optional: schedule daily generation

Run locally with cron (macOS/Linux):

```bash
crontab -e
```

Add (8 AM daily, adjust path):

```
0 8 * * * cd /path/to/quillcast && .venv/bin/python scripts/run_generate_post.py >> /tmp/quillcast.log 2>&1
```

Make sure `.env` is sourced in the cron job or API keys are exported in the crontab entry.

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

See [docs/PLAN.md](docs/PLAN.md) for the implementation roadmap:
- **Phase 5** — Cron automation (local)
