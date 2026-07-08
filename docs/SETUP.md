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

Local copies (gitignored) — run once after clone:

```bash
cp config/personas.example.yaml config/personas.yaml
cp config/platforms.example.yaml config/platforms.yaml
```

The committed `*.example.yaml` files are **minimal schemas** only. Customize your local copies using the reference below.

`AUTHOR_NAME` in `.env` overrides `author_name` in LLM prompts when set.

If a local file is missing, Quillcast falls back to the matching `*.example.yaml` so a fresh clone still runs.

**Personal backup (optional):** keep copies outside git in `config/local-backup/` (gitignored). Restore with:

```bash
cp config/local-backup/personas.yaml config/personas.yaml
cp config/local-backup/platforms.yaml config/platforms.yaml
```

---

### `config/platforms.yaml` — schema reference

| Key | Required | Description |
|-----|----------|-------------|
| `rss_categories` | No | Map of category id → `{ label }`. Use any ids you want (`tech`, `gaming`, `finance`, …). |
| `platforms.<name>.enabled` | Yes | `true` to generate/publish for that platform. Enable at least one for drafting. |
| `platforms.<name>.token_file` | For OAuth platforms | Path to token JSON (e.g. `data/tokens/linkedin.json`). |
| `platforms.blog.type` | For blog | Set to `ghost`. |
| `platforms.blog.default_status` | For blog | `draft` or `published`. |
| `platforms.blog.ghost_custom_templates.by_tag` | No | Map tag name → Ghost template slug (e.g. `Games: custom-games`). |
| `platforms.blog.ghost_custom_templates.by_persona` | No | Map persona id → Ghost template slug. |
| `rss_feeds.<key>.url` | Yes | RSS/Atom feed URL. |
| `rss_feeds.<key>.category` | Yes | Category id (must match `rss_categories` or any id used in personas). |
| `rss_filter.min_article_age_hours` | No | Skip articles newer than this (default `1`). |
| `rss_filter.max_article_age_hours` | No | Skip articles older than this (default `48`). |
| `rss_filter.max_articles_per_run` | No | Cap articles fetched per run (default `5`). |

**Example — enable LinkedIn + Ghost, two feed categories:**

```yaml
rss_categories:
  tech:
    label: Technology
  gaming:
    label: Gaming

platforms:
  linkedin:
    enabled: true
    token_file: data/tokens/linkedin.json
  blog:
    enabled: true
    type: ghost
    default_status: draft
    ghost_custom_templates:
      by_tag:
        Games: custom-games

rss_feeds:
  hn:
    url: https://hnrss.org/frontpage
    category: tech
  ign:
    url: https://feeds.feedburner.com/ign/all
    category: gaming
```

---

### `config/personas.yaml` — schema reference

Add **any number** of personas under `personas:` — the key is the persona id (shown in the Discover UI).

| Key | Required | Description |
|-----|----------|-------------|
| `default_persona` | Yes | Id of the persona selected by default. |
| `personas.<id>.label` | Yes | Display name in the UI. |
| `voice.author_name` | Yes | Used in prompts (overridden by `AUTHOR_NAME` in `.env`). |
| `voice.description` | Yes | Voice rules: tone, structure, opinion style, what to avoid. Be specific and behavioral, not just adjectives. |
| `voice.target_audience` | Yes | Who the post is for. |
| `voice.avoid_phrases` | No | Banned phrases and AI tells (e.g. "Let's dive in", "game-changer"). |
| `voice.voice_examples` | No | 1–2 short samples of **your** writing. The model uses the first two only — use your best real posts. |
| `rss_feed_keys` | No* | Explicit feed keys from `platforms.yaml`. |
| `rss_categories` | No* | Include all feeds in these categories. |
| `evergreen_topics` | No* | Fallback topic ideas when RSS is empty. |
| `blog_defaults.tags` | No | Default Ghost tags merged into blog drafts. |
| `blog_defaults.ghost_custom_template` | No | Ghost theme template slug for this persona (overrides `by_tag` / `by_persona`). |
| `curation_hint` | No | Extra guidance for the Discover topic-curation LLM call. |

\*Each persona needs at least one of: `rss_feed_keys`, `rss_categories`, or non-empty `evergreen_topics`.

**Linking feeds:** use `rss_feed_keys`, `rss_categories`, or both (union). Categories are defined in `platforms.yaml`.

**Example — two personas, different voices:**

```yaml
default_persona: tech

personas:
  tech:
    label: Tech & Engineering
    voice:
      author_name: Your Name
      description: >
        First person. Short paragraphs. Name specific tools and tradeoffs.
        State your opinion early. End with a real question, not filler.
      target_audience: Software engineers and tech leads
      avoid_phrases:
        - "Let's dive in"
        - "game-changer"
        - "leverage"
      voice_examples:
        - >
            We moved integration tests off the main deploy path. Deploy time
            dropped 40%. Nobody wanted to own staging until prod broke twice.
    rss_categories:
      - tech
    evergreen_topics:
      - A tool that failed me and what I use instead
    blog_defaults:
      tags: [AI, Engineering]
    curation_hint: Practitioner angles, shipping lessons — skip launch hype.

  gaming:
    label: Gaming
    voice:
      author_name: Your Name
      description: >
        A player, not a critic. What you're playing, worth it or skip,
        platform frustrations. Name the game and platform.
      target_audience: Gamers
      avoid_phrases:
        - "must-play masterpiece"
        - "gamers rejoice"
      voice_examples:
        - >
            Finished the game last week. Fifteen hours in I still hadn't touched
            the main quest. Worth it if you like sandbox more than story.
    rss_categories:
      - gaming
    evergreen_topics:
      - What I'm playing this week and whether it's worth your time
    blog_defaults:
      tags: [Games]
      ghost_custom_template: custom-games
```

**Tips for authentic voice**

- Put **real posts** in `voice_examples` (LinkedIn, blog) — trimmed, no hashtag spam.
- `description` should be rules the model can follow ("first person", "name companies", "blunt when broken").
- `evergreen_topics` work best as **your** story hooks, not generic titles.
- Use **More personality** in Review to re-draft with stronger voice.

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

Add evergreen topics under the relevant persona in `config/personas.yaml`, or check that RSS feeds are reachable.

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
