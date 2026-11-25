# Changelog

_Last updated: 2026-11-25_

All notable changes to this project are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

Add one line per meaningful change under `[Unreleased]`. Security-relevant changes are also noted in `SECURITY.md`.

## [Unreleased]

### Added
- 2026-11-25: engager (`harness/agents/engager.py`): checks the Telegram bot token, loads leads from Supabase, writes a personalized email per lead with the LLM, renders the HTML template `app/backend/data/assets/outreach_email.html` with the deep link; dry run by default, `--send` after confirmation.
- 2026-11-25: seller (`harness/agents/seller.py`): one-turn agent loop with `search_kb` and `send_voice_note` tools, `<e:name>` tag parser (`harness/parsers/tags.py`), text and sticker sending (`harness/tools/messaging.py`), voice notes with code checks (`harness/tools/audio_generator.py`).
- 2026-11-25: prompts for the seller and the engager (`harness/prompts/`), filled from the company profile; a company can override them in `gitignore/data/<company>/prompts/`.
- 2026-11-25: local RAG (`harness/RAG/`): LangChain recursive splitter, fastembed dense + BM25 sparse vectors in Milvus Lite, hybrid search with RRF.
- 2026-11-25: `core/start.py` (`ensure_rag`): checks the RAG before the API and dashboard start, builds it when missing, stops with an error when `RAG_DATA_DIR` has no documents.
- 2026-11-25: adapters in `services/`: `llm.py` (OpenAI-compatible), `gmail.py`, `telegram.py` (aiogram, sending only), `elevenlabs_tts.py`; provider interfaces in `services/interfaces.py`; `SupabaseRepository` for leads, start tokens, sends and tool calls.
- 2026-11-25: email and Telegram allowlists in `core/allowlists.py`; unit tests for the tag parser, allowlists, Gmail message building, voice-note checks, seller loop, engager and RAG.
- 2026-11-24: `messages.metadata` (jsonb) for Gmail threading fields, voice details and measured usage; the models, mock data and tests follow.
- 2026-11-21: `crm.company_description` (what the lead's company does) in `SCHEMA.sql`, the models, the mock data and the Leads page.
- 2026-11-20: `requirements.txt` (runtime dependencies, exported from `uv.lock`) for pip users.
- 2026-11-20: `SCHEMA.sql` and `SCHEMA.md`: Supabase schema (funnel tables, `email_drafts`, Braintrust-shaped `eval_*` tables), RLS on every table.
- 2026-11-20: generic knowledge-base collector (`app/backend/services/kb_scraper.py`) driven by `kb_sources` in the company profile.
- 2026-11-20: FastAPI backend (`/api/v1`: health, company, funnel, leads, conversations, masked, approvals, evals, logs, mock data) and `main.py` that starts it with the Streamlit dashboard.
- 2026-11-20: pitch-black Streamlit dashboard with an animated 3D orb (vendored three.js r149, MIT) and pages for overview, leads, conversations, safety, approvals, evals, logs and data.
- 2026-11-20: deletable mock data (`gitignore/temp/mock/`) so the dashboard can be previewed before real data exists.
- 2026-11-20: unit tests in `app/tests/` for the collector, mock data, API, schema and orb component.

### Changed
- 2026-11-25: seller system prompt rewritten: the agent chooses text or voice note for every reply, follows a medium the user asks for in the chat, and always sends text first. `/start` no longer asks for a mode; `pref_mode` is an optional `/settings` limit (null = agent decides). `send_voice_note` refuses before the first text (`first_message_text`). Docs follow.
- 2026-11-25: settings and `example.env` gain LLM, Telegram, Gmail sender, TTS, Supabase and RAG values; `EMBED_*` replaced by local fastembed models.
- 2026-11-24: `messages.message_type` (`text`, `voice`, `sticker`, `video`) replaces `transcript_source`; `audio_ref` removed because audio is never stored, only its transcript. `SCHEMA.sql` migrates existing databases; models, mock data (now with sticker rows), the Conversations page and tests follow.
- 2026-11-21: unified the project name spelling to Mrktr in the docs, code, UI title, API title, package name and User-Agent.
- 2026-11-21: README shows the Mrktr logo (`assets/mrktr_logo.png`).
- 2026-11-20: every doc file now carries a `Last updated` line; LICENSE year set to 2026.
- 2026-11-20: CLAUDE.md now cites `app/tests/`, `SCHEMA.*` and `assets/`.

### Removed
- 2026-11-25: knowledge-base scraper (`services/kb_scraper.py`) and its tests: documents are now provided in `gitignore/data/<company>/kb/` (or `RAG_DATA_DIR`).

### Fixed
- 2026-11-24: the unique index on messages is now `(user_id, channel, channel_message_id)`; Telegram message ids repeat across chats, so the old `(channel, channel_message_id)` index would have rejected valid messages.
- 2026-11-21: dashboard sidebar could not be reopened after collapsing (the CSS hid the toolbar that holds the expand button); it is kept visible now.
- 2026-11-21: replaced deprecated `use_container_width` with `width="stretch"` and `st.components.v1.html` with `st.iframe`.

### Security
- 2026-11-24: a Telegram id can be linked to only one user (unique index on `users.channel_ids->>'telegram'`).
- 2026-11-20: dashboard and API bind to `127.0.0.1` only; RLS enabled on all tables with no policies.
