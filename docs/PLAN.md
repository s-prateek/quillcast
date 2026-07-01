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

<<<<<<< HEAD
### 1.2 Config files
- [x] `config/platforms.yaml` (LinkedIn enabled, RSS feeds)
- [x] `config/topics.yaml` (voice + evergreen topics)

### 1.3 LinkedIn OAuth
- [ ] Register app at [LinkedIn Developer Portal](https://developer.linkedin.com/) — redirect URL `http://localhost:8080/callback`
- [ ] Request `w_member_social` scope
- [ ] Run: `python scripts/linkedin_oauth.py`
- [ ] Confirm tokens at `data/tokens/linkedin.json`

**Phase 1 done when:** Config files exist, OAuth tokens saved locally.
=======
### 1.2 CDK — StorageStack
- [x] Initialise CDK app (`cdk/app.py` + `cdk/stacks/storage_stack.py` created manually)
- [x] Define DynamoDB table `quillcast-drafts` (On-Demand billing, `PostID` as PK)
- [x] Add GSI: `OverallStatus-CreatedAt-index` (PK: `OverallStatus`, SK: `CreatedAt`)
- [x] Define S3 bucket for config files — CDK generates unique name including account ID
- [x] Refresh AWS credentials, then `cdk bootstrap` (one-time per account/region)
- [x] `cdk deploy QuillcastStorageStack` — verify resources appear in AWS console

### 1.3 Config files in S3
- [x] Write `config/platforms.yaml` (LinkedIn enabled, Facebook + blog disabled)
- [x] Write `config/topics.yaml` (voice description + 8 evergreen topics)
- [x] Upload both to S3 after deploy: `aws s3 cp config/ s3://<ConfigBucketName>/config/ --recursive`

### 1.4 LinkedIn OAuth
- [x] Register app at [LinkedIn Developer Portal](https://developer.linkedin.com/) — add `http://localhost:8080/callback` as redirect URL
- [x] Request `w_member_social` permission scope (may take a few days for approval)
- [ ] Enable Amazon Bedrock Claude Haiku model access in your AWS region via the [Bedrock console](https://console.aws.amazon.com/bedrock/)
- [x] Run OAuth flow: `export LINKEDIN_CLIENT_ID=... LINKEDIN_CLIENT_SECRET=... && python scripts/linkedin_oauth.py`
- [x] Confirm tokens stored: `aws ssm get-parameter --name /quillcast/linkedin/tokens --with-decryption`

**Phase 1 done when:** DynamoDB table and S3 bucket exist in AWS, config files are uploaded,
LinkedIn tokens are in SSM and verified, `cdk synth` passes cleanly. ✅ `cdk synth` already passes.
>>>>>>> origin/main

---

## Phase 2 — Content Generation
*Goal: Running the script picks a topic, calls Claude/Gemini, and writes a local draft.*

<<<<<<< HEAD
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
=======
### 2.1 Shared models
- [x] `shared/models.py` — `PostRecord`, `PostContent`, `PublishResult` dataclasses
- [x] `shared/dynamodb.py` — helpers: `put_record()`, `get_record()`, `update_target_status()`
- [x] `shared/config.py` — loads `platforms.yaml` and `topics.yaml` from S3

### 2.2 RSS fetcher
- [x] `lambdas/generate_post/rss.py` — fetch + parse configured RSS feeds using `feedparser`
- [x] Filter by `min_article_age_hours` / `max_article_age_hours`
- [x] Return ranked list of `(title, url, summary)` tuples

### 2.3 Bedrock call
- [x] `lambdas/generate_post/bedrock.py` — build the structured prompt (see `design.md §5`)
- [x] Invoke `anthropic.claude-haiku-4-5` via `boto3` Bedrock Runtime client
- [x] Parse JSON response into `ContentVariants` dict
- [x] Handle malformed JSON responses with a retry (max 2 attempts)

### 2.4 Lambda handler
- [x] `lambdas/generate_post/handler.py` — wire together: fetch topics → select best → call Bedrock → write DynamoDB
- [x] `lambdas/generate_post/requirements.txt` (`boto3`, `feedparser`)

### 2.5 CDK — LambdaStack (generation)
- [x] Define `generate_post` Lambda (Python 3.12, 512 MB, 5 min timeout)
- [x] IAM role: `bedrock:InvokeModel`, `dynamodb:PutItem`, `s3:GetObject`
- [ ] `cdk deploy QuillcastLambdaStack`
- [ ] Invoke manually: `aws lambda invoke --function-name quillcast-generate-post out.json`
- [ ] Verify record appears in DynamoDB with `OverallStatus: PENDING`

**Phase 2 done when:** A DynamoDB record exists with properly formatted `ContentVariants`
and `OverallStatus: PENDING`.
>>>>>>> origin/main

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
