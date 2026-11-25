# CLAUDE.md — mrktr AI

_Last updated: 2026-11-25_

## What this project is
**mrktr AI** is a general, modular go-to-market (GTM) agent. Given a company profile and its documents, it runs a measured outreach funnel:

1. **First touch — Gmail:** a short personalized email with a Telegram deep link (`t.me/<bot>?start=<token>`).
2. **Conversation — Telegram:** the agent qualifies the lead, answers from the company's knowledge base, and decides when to reply with text, a sticker or a voice note.
3. **Outcome:** CRM update, booking link, and tutorial videos (Remotion) for "how does X work?" questions.
4. **Replies:** incoming emails are sorted and answered with drafts that a human approves.

Every step is logged and measured. Guards, prompt-injection masking, evals and security tests run throughout.

**The harness is company-agnostic.** Everything specific to one company (profile, persona, documents, CRM, stickers, prompts) lives in `gitignore/data/` and is never committed. Swapping that folder must produce a new deployment without touching code.

License: **Apache 2.0**.

## Repository structure
Keep this structure. Don't add top-level folders without asking. Files that `uv` adds (`pyproject.toml`, `uv.lock`, `.python-version`, `.venv/`) are expected.

```
mrktr AI/
├── .claude/                     # Claude Code settings, commands, hooks
├── assets/                      # brand assets (logo)
├── app/
│   ├── backend/
│   │   ├── core/                # settings, logging, provider registry, allowlists, errors, start (RAG check)
│   │   ├── data/
│   │   │   ├── assets/          # generic email templates (outreach_email.html)
│   │   │   ├── models/          # pydantic + table models (users, crm, messages, masked_messages, events…)
│   │   │   └── repositories/    # Supabase/Postgres access; SQL functions and analytics queries
│   │   ├── endpoints/v1/        # FastAPI routers (health, admin actions for the dashboard, tutorials, logs)
│   │   ├── harness/             # agents (engager, seller), tools, prompts, tag parser, RAG, masking, evals
│   │   └── services/            # adapters: LLM, guards, TTS/STT, Gmail, Telegram, Remotion
│   ├── streamlit/               # local dashboard (funnel, CRM, conversations, masked messages, approvals, evals, API logs)
│   └── tests/                   # unit tests: tools, tag parser, masking, allowlists
├── docs/                        # public docs: architecture, setup, examples (incl. a fictional sample company)
├── gitignore/                   # IGNORED BY GIT — never commit anything here
│   ├── data/                    # company profiles, KB sources, CRM exports, persona, prompts, stickers
│   ├── docs/                    # private notes and documents
│   └── temp/                    # logs, generated audio, rendered videos, caches
├── .gitignore
├── CHANGELOG.md
├── CLAUDE.md
├── DECISIONS.md                 # "X over Y because Z"
├── LICENSE                      # Apache 2.0
├── main.py                      # single entry point: starts FastAPI + Streamlit
├── README.md
├── SCHEMA.md                    # database schema, explained
├── SCHEMA.sql                   # run in Supabase to create the schema (source of truth)
└── SECURITY.md
```

### Where things go
| Concern | Location |
|---|---|
| Settings (pydantic-settings, `.env`), logging setup, provider registry | `app/backend/core/` |
| Allowlists (email recipients, Telegram users) | `app/backend/core/` |
| Table/DTO models | `app/backend/data/models/` |
| DB reads/writes, RLS-aware queries, growth SQL | `app/backend/data/repositories/` |
| HTTP API | `app/backend/endpoints/v1/` |
| Agent loop, tools, prompts, `<e:…>` parser, masking, eval suites | `app/backend/harness/` |
| External integrations (one adapter per provider) | `app/backend/services/` |
| Dashboard pages | `app/streamlit/` |
| Unit tests | `app/tests/` |
| Database schema | `SCHEMA.sql` (+ `SCHEMA.md`) |
| Mock data for the dashboard | `app/backend/data/mock.py` writes to `gitignore/temp/mock/` |
| Generic email templates | `app/backend/data/assets/` |
| Startup checks (RAG index) | `app/backend/core/start.py` |
| Company-specific anything | `gitignore/data/<company>/` |
| Runtime artifacts (logs, audio, video) | `gitignore/temp/` |

## Running
`main.py` is the only entry point. It:
1. Loads settings and the active company profile (`ACTIVE_COMPANY` → `gitignore/data/<company>/`), then runs `core/start.py:ensure_rag`: builds the local RAG index (Milvus Lite in `gitignore/temp/rag/`) from `RAG_DATA_DIR` (default `gitignore/data/<company>/kb/`) if it is missing, and stops with an error if there are no documents.
2. Starts **FastAPI** (uvicorn) and the **Telegram bot** (long polling, inside the FastAPI lifespan).
3. Starts **Streamlit** as a subprocess.
4. Writes FastAPI/bot logs to `gitignore/temp/logs/api.log` (rotating). The Streamlit dashboard has a page that tails this file, so API logs are visible from the dashboard.
5. Shuts both down cleanly on Ctrl+C.

```bash
uv sync
uv run main.py            # FastAPI on :8000, Streamlit on :8501
```

## Company profile (`gitignore/data/<company>/`)
```
company.yaml        # name, website, products/plans, ICP, qualification questions,
                    # persona (name, tone, languages), disclaimer text, booking link
kb/                 # source documents for RAG (public material only, with collection dates)
stickers.yaml       # expression name → Telegram sticker file_id
prompts/            # system prompt + tool instructions for this company
crm/                # raw exports (e.g. form responses) before import
```
- A fictional sample lives in `docs/examples/` so the repo runs without private data.
- The **disclaimer** in `company.yaml` (e.g. "unofficial demo, not affiliated with X") is shown in every email, the bot's `/start` message and the dashboard whenever it's set.

## Providers (agnostic by design)
All external services sit behind an interface in `app/backend/services/`, chosen by settings. Never hard-code a provider in the harness.

| Capability | Interface | Adapters | Settings |
|---|---|---|---|
| LLM (chat + tools, streaming) | OpenAI-compatible client | **OpenRouter**, **Venice AI** | `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` |
| Content safety | `ContentGuard` | Llama Guard via an OpenAI-compatible provider | `GUARD_PROVIDER`, `GUARD_MODEL`, `GUARD_API_KEY` |
| Injection detection | `InjectionGuard` | Prompt Guard (local, Hugging Face) | `INJECTION_GUARD_MODEL` |
| Text-to-speech | `TTSProvider` | ElevenLabs | `TTS_PROVIDER`, `TTS_API_KEY`, `TTS_VOICE_ID` |
| Speech-to-text | `STTProvider` | ElevenLabs | `STT_PROVIDER`, `STT_API_KEY` |
| Tutorial videos | `TutorialRenderer` | Remotion render endpoint | `REMOTION_ENDPOINT`, `REMOTION_API_KEY` |
| Embeddings + RAG | `harness/RAG/` | fastembed (local dense + BM25) in Milvus Lite (local file) | `RAG_DATA_DIR`, `RAG_DENSE_MODEL`, `RAG_SPARSE_MODEL` |
| Email | `EmailChannel` | Gmail API | `GMAIL_CREDENTIALS_PATH`, `GMAIL_SENDER` |
| Chat | `ChatChannel` | Telegram Bot API | `TELEGRAM_BOT_TOKEN` |
| Evals | `EvalBackend` | Braintrust | `BRAINTRUST_API_KEY` |
| Database | repositories | Supabase (Postgres + pgvector) | `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL` |

- Provider features differ (tool calling, streaming, model names). Check capability at startup and fail with a clear message instead of degrading silently.
- Keep a provider's quirks (headers, model IDs, audio formats) inside its adapter.
- Adding a provider means adding an adapter and a settings value, nothing else.

## Data model
```
users(user_id, channel_ids, email, start_token, pref_mode, consent_at, company)
crm(user_id, company_name, company_description, role, industry, size, use_case, budget, timeline, status)
messages(id, user_id, channel, channel_message_id, direction,
         message_type [text|voice|sticker|video], text,
         metadata jsonb, created_at)   # metadata: Gmail thread/headers, voice duration, sticker set, video ref, measured usage
masked_messages(id, message_id, original_text, masked_text,
                detector, score, reason, created_at)          # RLS: owner only
tool_calls(id, user_id, tool, args, result, refused_reason, created_at)
events(id, user_id, type, payload, created_at)               # email_sent, token_redeemed, mode_chosen, qualified, booked…
kb_chunks(id, company, source, collected_at, content, embedding)   # unused for now: RAG is local Milvus Lite
```
- Save a transcript for every message: typed text, speech-to-text, agent text or TTS script; `message_type` + `direction` tell which. **Audio is never stored**, only its transcript. Stickers store the expression name (out) or the sticker's emoji (in).
- `SCHEMA.sql` is the source of truth for tables; it also holds `email_drafts` (approval queue) and the Braintrust-shaped `eval_*` tables. Keep `data/models/tables.py` in step with it.
- Analytics are hand-written SQL in `data/repositories/`, one query per metric, each with a comment on what it measures.

## Agent behaviour
- **Tools:** `lookup_lead`, `search_kb`, `update_crm`, `send_tutorial`, `send_voice_note`, `send_booking_link`.
- **The agent chooses the medium** of every reply (text or voice note, plus at most one sticker). The user decides only by asking for a medium in the chat; the agent then follows that request until asked otherwise (prompt-level, see `harness/prompts/system_prompt.py`).
- **First message is always text** (AI disclosure + disclaimer), in the prompt and in code.
- **Hard limit** (`pref_mode`, optional, set with `/settings`, not asked on `/start`): *Text only* (voice refused in code), *Audio + transcript*, *Audio only*. Null = no limit, the agent decides.
- **Stickers:** at most one `<e:name>` tag per text reply. The parser buffers until the tag closes, validates the name against `stickers.yaml` (unknown → no sticker), strips the tag and sends the sticker. Tags never trigger audio.
- **Voice notes:** only through the `send_voice_note(text)` tool, which checks in code, in this order:
  1. user is allowlisted (valid token + consent);
  2. user's `/settings` limit allows audio (`text_only` → refuse and tell the agent);
  3. a text was already sent in this conversation (the first message is text → `first_message_text`);
  4. content guard passes on the text;
  5. max length (~60 s of speech);
  6. rate limit (≤ 1 per turn, a cap per conversation);
  7. TTS → convert to the channel's format (Telegram: OGG/Opus, ffmpeg if needed) → send → log, refusals included.
- **Tutorials:** `send_tutorial(topic)` calls the Remotion endpoint with a script built from the KB, stores the video in `gitignore/temp/`, and sends it or its link.
- **Masking:** split incoming text into sentences, score each with the injection and content guards, replace flagged sentences with `[removed: possible prompt injection]` before the LLM sees them, store originals in `masked_messages`, and keep answering the rest normally.

## Hard rules
1. **Never commit anything from `gitignore/`, `.env`, keys, tokens, CRM data, KB content or prompts for a real company.** Run a secret scan (e.g. gitleaks) in the pre-push hook.
2. **Allowlists live in code** (`app/backend/core/`). Email goes only to allowlisted recipients; the Telegram bot replies only to users who redeemed a valid start token and have consent on record. Never weaken them or make them controllable by the prompt or the LLM.
3. **No outbound action without explicit approval:** never send an email, message a user, or write to a non-dev database without the owner confirming. Default to the dev database, a dev bot and test accounts.
4. **Never make a failing eval pass by changing the test, its threshold or its dataset.** Fix the code or report the failure.
5. **Audio is produced only through `send_voice_note` and its checks.** No other path from model output to TTS.
6. **Masked originals are stored only in `masked_messages`.** Never log raw attack text elsewhere.
7. **Disclose the AI.** The agent says it's an AI on first contact, and the company profile's disclaimer is always shown when set.
8. **Personal data:** collect only what the funnel needs, with consent; support deleting a user and everything linked to them.
9. **No company-specific code** in `app/`. If something only makes sense for one company, it belongs in its profile.
10. **New dependencies must be license-compatible with Apache 2.0.** Note notable ones in `README.md`.

## Evals and security tests
Eval suites live in `app/backend/harness/` and run against Braintrust; results can be shown in the dashboard.
- **Performance:** qualification accuracy, CRM write correctness, KB answer accuracy, STT accuracy, email reply-sorting accuracy, tag validity rate, sticker-mood match (LLM judge), voice-note decision quality (LLM judge), voice notes per conversation, latency, cost per conversation.
- **Security:** masking precision/recall, injection success after masking, benign-decoy hijack rate, unsafe-content rate, PII leak rate, recipient-redirect attempts blocked, replies to non-allowlisted users (must be 0), voice notes to text-only users (must be 0), injected instructions that trigger a tool, false claims about the company.
- Compare versions (v1 → v2) and runs before/after guards.

## Funnel metrics (dashboard)
Email click-through (token redemptions / emails sent) · voice vs text replies · % who reply · turns per conversation · % qualified · bookings · cost per qualified lead · time from email to first reply · reply-sorting accuracy · % of drafts approved unchanged.

## Working conventions
- **Before any non-trivial change, propose 2 options with trade-offs and wait for a choice.**
- Small steps: one feature, show the diff, run tests, commit.
- Every Markdown doc has a `Last updated: YYYY-MM-DD` line under its title: update it when you edit the file.
- After each meaningful change: add a line to `CHANGELOG.md`; suggest a `DECISIONS.md` entry when a design choice was made.
- Security-relevant changes (allowlists, guards, masking, auth, data retention) are also noted in `SECURITY.md`.
- Flag scope creep instead of silently expanding the task.
- Never fabricate results, metrics or claims about a company; use measured numbers only.

## Code style
- Python 3.11+, managed with `uv`. Type hints everywhere; ruff (lint + format).
- Pydantic models for settings, tool inputs/outputs and API schemas.
- Async for I/O (FastAPI, bot, provider calls).
- Each module imports from `core/` and `services/` interfaces, never from a concrete adapter outside `services/`.
- SQL: lowercase keywords, one file or function per query, a comment on what each metric means.
- Every tool, the tag parser, masking and the allowlists have unit tests in `app/tests/`.

## Commands
```bash
uv sync                      # install
uv run main.py               # FastAPI + Telegram bot + Streamlit
uv run ruff check . && uv run ruff format .
uv run pytest app/tests      # unit tests
uv run python -m app.backend.services.gmail authorize     # once: Gmail OAuth (browser)
uv run python -m app.backend.harness.agents.engager       # first-touch emails: dry run, previews in gitignore/temp/outbox/
uv run python -m app.backend.harness.agents.engager --send   # sends after typed confirmation, allowlisted only
```
