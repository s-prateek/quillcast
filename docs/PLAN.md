# Quillcast — Implementation Plan

Phases are sequential. Each phase ends with something that works end-to-end so you can
test before moving on. Check off tasks as you complete them.

---

## Phase 1 — Foundation
*Goal: AWS infrastructure is live, LinkedIn OAuth works, you can write a record to DynamoDB manually.*

### 1.1 Project scaffold
- [x] Set up `pyproject.toml` with dev dependencies (`boto3`, `pytest`, `ruff`, `aws-cdk-lib`)
- [x] Create folder structure per `design.md` (empty `__init__.py` files where needed)
- [x] Create `.env.example` documenting all required environment variables
- [x] Verify `.gitignore` is catching `.env`, `cdk.out/`, `__pycache__/`

### 1.2 CDK — StorageStack
- [x] Initialise CDK app (`cdk/app.py` + `cdk/stacks/storage_stack.py` created manually)
- [x] Define DynamoDB table `quillcast-drafts` (On-Demand billing, `PostID` as PK)
- [x] Add GSI: `OverallStatus-CreatedAt-index` (PK: `OverallStatus`, SK: `CreatedAt`)
- [x] Define S3 bucket for config files — CDK generates unique name including account ID
- [ ] Refresh AWS credentials, then `cdk bootstrap` (one-time per account/region)
- [ ] `cdk deploy QuillcastStorageStack` — verify resources appear in AWS console

### 1.3 Config files in S3
- [x] Write `config/platforms.yaml` (LinkedIn enabled, Facebook + blog disabled)
- [x] Write `config/topics.yaml` (voice description + 8 evergreen topics)
- [ ] Upload both to S3 after deploy: `aws s3 cp config/ s3://<ConfigBucketName>/config/ --recursive`

### 1.4 LinkedIn OAuth
- [ ] Register app at [LinkedIn Developer Portal](https://developer.linkedin.com/) — add `http://localhost:8080/callback` as redirect URL
- [ ] Request `w_member_social` permission scope (may take a few days for approval)
- [ ] Enable Amazon Bedrock Claude Haiku model access in your AWS region via the [Bedrock console](https://console.aws.amazon.com/bedrock/)
- [ ] Run OAuth flow: `export LINKEDIN_CLIENT_ID=... LINKEDIN_CLIENT_SECRET=... && python scripts/linkedin_oauth.py`
- [ ] Confirm tokens stored: `aws ssm get-parameter --name /quillcast/linkedin/tokens --with-decryption`

### 1.5 Telegram bot *(optional — for push notifications only)*
- [ ] Create bot via @BotFather, copy `bot_token`
- [ ] Send a message to the bot, then run: `python scripts/get_telegram_chat_id.py`
- [ ] Verify it works: `export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... && python scripts/test_telegram.py`
- [ ] Store in SSM:
  ```
  aws ssm put-parameter --name /quillcast/telegram/bot_token --value "..." --type SecureString
  aws ssm put-parameter --name /quillcast/telegram/chat_id   --value "..." --type String
  ```

**Phase 1 done when:** DynamoDB table and S3 bucket exist in AWS, config files are uploaded,
LinkedIn tokens are in SSM and verified, `cdk synth` passes cleanly. ✅ `cdk synth` already passes.

---

## Phase 2 — Content Generation
*Goal: Running the Lambda (or the script locally) picks a topic, calls Bedrock, and writes a record to DynamoDB. Telegram notification fires.*

### 2.1 Shared models
- [ ] `shared/models.py` — `PostRecord`, `PostContent`, `PublishResult` dataclasses
- [ ] `shared/dynamodb.py` — helpers: `put_record()`, `get_record()`, `update_target_status()`
- [ ] `shared/config.py` — loads `platforms.yaml` and `topics.yaml` from S3

### 2.2 RSS fetcher
- [ ] `lambdas/generate_post/rss.py` — fetch + parse configured RSS feeds using `feedparser`
- [ ] Filter by `min_article_age_hours` / `max_article_age_hours`
- [ ] Return ranked list of `(title, url, summary)` tuples

### 2.3 Bedrock call
- [ ] `lambdas/generate_post/bedrock.py` — build the structured prompt (see `design.md §5`)
- [ ] Invoke `anthropic.claude-haiku-4-5` via `boto3` Bedrock Runtime client
- [ ] Parse JSON response into `ContentVariants` dict
- [ ] Handle malformed JSON responses with a retry (max 2 attempts)

### 2.4 Lambda handler
- [ ] `lambdas/generate_post/handler.py` — wire together: fetch topics → select best → call Bedrock → write DynamoDB → send Telegram notification
- [ ] `lambdas/generate_post/requirements.txt` (`boto3`, `feedparser`)

### 2.5 CDK — LambdaStack (generation)
- [ ] Define `generate_post` Lambda (Python 3.12, 512 MB, 5 min timeout)
- [ ] IAM role: `bedrock:InvokeModel`, `dynamodb:PutItem`, `s3:GetObject`, `ssm:GetParameter`
- [ ] `cdk deploy LambdaStack`
- [ ] Invoke manually: `aws lambda invoke --function-name quillcast-generate-post out.json`
- [ ] Verify record appears in DynamoDB with `OverallStatus: PENDING`

**Phase 2 done when:** A DynamoDB record exists with properly formatted `ContentVariants`
and a Telegram message arrives on your phone.

---

## Phase 3 — Publisher
*Goal: Calling the publish Lambda posts the LinkedIn variant to LinkedIn and updates DynamoDB.*

### 3.1 Publisher abstraction
- [ ] `publishers/base.py` — `Publisher` ABC with `publish()`, `validate_credentials()`, `get_constraints()`, `render_preview()`
- [ ] `publishers/registry.py` — maps platform string → Publisher class, loaded from `platforms.yaml`

### 3.2 LinkedIn publisher
- [ ] `publishers/linkedin.py` — implement `Publisher`
  - [ ] Load tokens from SSM
  - [ ] Proactive refresh: if `token_expiry` within 7 days, refresh and update SSM
  - [ ] `POST /rest/posts` with correct headers (`LinkedIn-Version`, `X-Restli-Protocol-Version`)
  - [ ] Exponential backoff on 429 (max 3 retries, base 2s, add jitter)
  - [ ] `get_constraints()` returns `{"char_limit": 3000, "supports_images": True}`
  - [ ] `render_preview()` returns LinkedIn card HTML (profile area + post text + reaction bar)

### 3.3 publish_post Lambda
- [ ] `lambdas/publish_post/handler.py` — receive `{post_id, platform}`, load record, call publisher, update DynamoDB
- [ ] `lambdas/publish_post/requirements.txt`

### 3.4 CDK — LambdaStack (publisher)
- [ ] Add `publish_post` Lambda + **Function URL** (IAM auth) to LambdaStack
- [ ] IAM role: `dynamodb:GetItem UpdateItem`, `ssm:GetParameter GetParametersByPath`, `ssm:PutParameter`
- [ ] `cdk deploy LambdaStack`
- [ ] Test: invoke with a real `post_id` from Phase 2, verify post appears on LinkedIn

**Phase 3 done when:** A post goes live on LinkedIn via a manual Lambda invocation and
DynamoDB shows `Status: POSTED` with a `PlatformPostID`.

---

## Phase 4 — Review UI
*Goal: `streamlit run ui/app.py` shows pending drafts with a LinkedIn preview, lets you edit, and publishes via the Lambda Function URL.*

### 4.1 LinkedIn preview component
- [ ] `ui/components/linkedin_preview.py` — renders a LinkedIn card as HTML
  - Profile picture placeholder + author name + headline (from `config/topics.yaml` author section)
  - Post text with `...see more` truncation at 210 chars
  - Reaction bar (cosmetic)
  - Character counter with colour coding (green < 2500, amber 2500–2900, red > 2900)

### 4.2 Platform tab component
- [ ] `ui/components/platform_tab.py` — generic tab: calls `publisher.render_preview()` + editable `st.text_area` + publish/skip/archive buttons

### 4.3 Streamlit app
- [ ] `ui/app.py`
  - Sidebar: list all `PENDING` drafts (query DynamoDB GSI)
  - Main panel: topic title + source link + creation date
  - One tab per enabled platform
  - "Publish" button: `POST` to `publish_post` Function URL with `{post_id, platform, edited_content}`
  - "Archive" button: updates `Target.Status` to `ARCHIVED` directly via boto3
- [ ] `ui/requirements.txt` (`streamlit`, `boto3`, `requests`)
- [ ] `ui/.env.example` (Function URL, AWS region, profile config)

**Phase 4 done when:** You can open the UI, see a real draft from DynamoDB, edit the text,
hit Publish, and see the post go live on LinkedIn without touching the terminal.

---

## Phase 5 — Automation
*Goal: The whole pipeline runs daily without any manual action. Failed runs are captured.*

- [ ] CDK `SchedulerStack`:
  - [ ] EventBridge Scheduler cron (e.g. `cron(0 8 * * ? *)` = 8 AM UTC daily)
  - [ ] Dead Letter Queue (SQS) for failed `generate_post` invocations
  - [ ] Lambda permission for EventBridge to invoke `generate_post`
- [ ] `cdk deploy SchedulerStack`
- [ ] Set AWS Budget alert at **$5/month** in the console (one-time manual step)
- [ ] Let it run for 3 days and verify 3 Telegram notifications + 3 DynamoDB records
- [ ] Check DLQ is empty (no failed runs)

**Phase 5 done when:** Drafts appear in DynamoDB every morning without you doing anything.

---

## Phase 6 — Open Source Prep
*Goal: A stranger can clone the repo, follow the README, and have their own Quillcast running.*

- [ ] Write `README.md`:
  - What it does + architecture diagram (copy from `design.md`)
  - Prerequisites (AWS account, LinkedIn Developer App, Telegram bot)
  - Step-by-step setup (Phase 1–5 condensed)
  - How to add a new platform
- [ ] `publishers/facebook.py` — stub with `NotImplementedError` and a docstring explaining the API
- [ ] `publishers/blog/ghost.py` — same
- [ ] `CONTRIBUTING.md` — how to add a publisher, code style, PR process
- [ ] Final check: `git log` contains no `.env` files, tokens, or real credentials anywhere in history

**Phase 6 done when:** You'd be comfortable sharing the GitHub link publicly.

---

## Future Ideas (post-v1)
- Scheduled publishing (`ScheduledFor` field + a poller Lambda)
- Image generation via Bedrock Titan Image / Stability AI for post visuals
- Facebook publisher
- Ghost/WordPress blog publisher
- Post performance tracking (pull engagement metrics back into DynamoDB)
- Web-hosted UI option (once the local workflow is proven)
