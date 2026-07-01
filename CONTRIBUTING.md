# Contributing to Quillcast

Thanks for your interest in Quillcast. This project is a **local-first** content pipeline: discover topics from RSS, generate drafts with Claude or Gemini, review in Streamlit, and publish to LinkedIn.

## Development setup

```bash
git clone https://github.com/s-prateek/quillcast.git
cd quillcast

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -r ui/requirements.txt   # optional, for UI work

cp .env.example .env
# Add GEMINI_API_KEY or ANTHROPIC_API_KEY
```

Full walkthrough: [docs/SETUP.md](docs/SETUP.md)

## Running the app

```bash
streamlit run ui/app.py --server.headless true
```

Open http://localhost:8501 manually.

## Code quality

```bash
ruff check .
pytest
```

CI runs the same checks on every pull request to `main`.

## Project layout

| Path | Purpose |
|------|---------|
| `shared/` | Core logic: RSS, LLM, drafts, discover, publish |
| `publishers/` | Platform API integrations |
| `ui/` | Streamlit Discover + Review UI |
| `config/` | YAML config (platforms, voice, RSS feeds) |
| `scripts/` | CLI helpers (generate, publish, OAuth) |
| `tests/` | Unit tests |

Architecture details: [docs/design.md](docs/design.md)

## Adding a platform publisher

1. Create `publishers/<platform>.py` implementing `Publisher` in `publishers/base.py`:
   - `publish()` — post content to the platform API
   - `validate_credentials()` — check token file / env
   - `get_constraints()` — char limits, media support
   - `render_preview()` — HTML for the Streamlit preview card

2. Register the class in `publishers/registry.py`.

3. Add platform config to `config/platforms.yaml`:
   ```yaml
   platforms:
     myplatform:
       enabled: true
       token_file: data/tokens/myplatform.json
   ```

4. Add tests under `tests/` (mock HTTP calls; no real API keys in CI).

5. Update `docs/SETUP.md` if OAuth or setup steps are required.

See `publishers/linkedin.py` for a full reference and `publishers/facebook.py` for a stub.

## Pull requests

1. Branch from `main`: `git checkout -b feat/your-feature`
2. Keep changes focused — one feature or fix per PR
3. Run `ruff check .` and `pytest`
4. Open a PR using the template in `.github/pull_request_template.md`

## Secrets and privacy

**Never commit:**

- `.env` or real API keys
- `data/` (drafts and OAuth tokens)
- Personal OAuth tokens or access credentials

Use placeholders in examples: `Your Name`, `sk-ant-...`, `AIza...`.

If you accidentally commit a secret, rotate the key immediately and do not rely on a follow-up commit to remove it from git history.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
