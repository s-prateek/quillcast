# Contributing to Quillcast

Thanks for your interest in contributing. Quillcast is open source, but **all changes merge through pull requests** reviewed by the maintainer.

> **Maintainers:** repo governance rules (branch protection, CODEOWNERS, CI) are documented in [docs/opensource-repo-governance.md](docs/opensource-repo-governance.md) for reuse across projects.

## Before you start

1. Read [README.md](README.md) for project overview and setup.
2. Check [docs/PLAN.md](docs/PLAN.md) for what's already planned or in progress — open an issue before large changes to avoid duplicate work.
3. See [docs/design.md](docs/design.md) for architecture and data model.

## How to contribute

### 1. Fork and branch

```bash
git clone https://github.com/<your-username>/quillcast.git
cd quillcast
git remote add upstream https://github.com/s-prateek/quillcast.git
git checkout -b feat/short-description
```

Use branch prefixes like `feat/`, `fix/`, or `docs/`.

### 2. Set up locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-cdk.txt -r requirements-dev.txt
cp .env.example .env   # fill in your own values — never commit .env
```

### 3. Make your changes

- Keep PRs **focused** — one logical change per PR is easier to review.
- Match existing code style and patterns.
- Add or update tests when behavior changes.
- Update docs if you change setup, config, or architecture.

### 4. Run checks locally

CI runs the same commands on every PR:

```bash
ruff check .
pytest
```

Optional before opening a PR:

```bash
cdk synth   # if you changed CDK stacks
```

### 5. Open a pull request

Push your branch and open a PR against `main` on the upstream repo. The PR template will guide you through the checklist.

- **Do not push directly to `main`.**
- Wait for CI (`lint-and-test`) to pass.
- Address review feedback; new commits should stay on the same branch.

## Credentials and security

**Never commit:**

- `.env` files or real API keys
- LinkedIn client secrets or OAuth tokens
- AWS access keys
- SSM parameter values
- Personal data in `config/topics.yaml` (use placeholders in examples)

All runtime secrets belong in **AWS SSM Parameter Store** (or local `.env` for development only). See [.env.example](.env.example).

If you accidentally commit a secret, rotate it immediately and force-push is **not** enough — assume the secret is compromised.

## What to contribute

Great first contributions:

- **Platform publishers** — implement `publishers/<platform>.py` (see `publishers/base.py` and [Adding a New Platform](README.md#adding-a-new-platform))
- **Tests** — especially for `shared/`, `lambdas/`, and `publishers/`
- **Documentation** — setup guides, troubleshooting, architecture clarifications
- **Bug fixes** — with a test that reproduces the issue

Check [docs/PLAN.md](docs/PLAN.md) for the current phase roadmap before starting large features.

## Code style

- **Python 3.9+** syntax (project target); Lambda runs 3.12.
- **Ruff** for linting — config in [pyproject.toml](pyproject.toml).
- Prefer clear names over comments; comment only non-obvious logic.
- No drive-by refactors unrelated to your PR.

## Adding a new platform publisher

1. Create `publishers/<platform>.py` implementing the `Publisher` interface.
2. Add a stub or full implementation; register in `publishers/registry.py` when that exists.
3. Set `enabled: true` in `config/platforms.yaml` with an `ssm_token_key`.
4. Add tests for API parsing, error handling, and constraint helpers.
5. Document OAuth setup steps in the PR description.

## Reporting bugs

Open a [GitHub issue](https://github.com/s-prateek/quillcast/issues) with:

- What you expected vs what happened
- Steps to reproduce
- Relevant logs (redact tokens and account IDs)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
