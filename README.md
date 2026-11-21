<p align="center">
  <img src="assets/mrktr_logo.png" alt="Mrktr" width="160">
</p>

# mrktr AI

_Last updated: 2026-11-21_

A general, modular go-to-market (GTM) agent. Give it a company profile and the company's documents, and it runs a measured outreach funnel: **Gmail starts the conversation, Telegram carries it.**

> **Disclaimer:** when a company profile sets one, its disclaimer (for example "unofficial demo, not affiliated with X") is shown in every email, in the bot's `/start` message and in the dashboard. The agent always says it is an AI on first contact.

## How the funnel works

1. **First touch (Gmail):** a short personalized email with a Telegram deep link (`t.me/<bot>?start=<token>`).
2. **Conversation (Telegram):** the agent qualifies the lead, answers from the company's knowledge base, and decides whether to reply with text, a sticker or a voice note.
3. **Outcome:** CRM update, booking link, and tutorial videos (Remotion) for "how does X work?" questions.
4. **Replies:** incoming emails are sorted and answered with drafts that a human approves.

Every step is logged and measured. Guards, prompt-injection masking, evals and security tests run throughout.

## Company-agnostic by design

The harness contains no company-specific code. Everything specific to one company (profile, persona, documents, CRM, stickers, prompts) lives in `gitignore/data/<company>/` and is never committed. Swapping that folder gives a new deployment without touching the code. A fictional sample company in `docs/examples/` lets the repo run without private data.

External services (LLM, guards, TTS/STT, email, chat, evals, database) sit behind interfaces chosen by settings, so adding a provider means adding an adapter and a setting.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and the Python version in `.python-version`.

```bash
uv sync
cp example.env .env        # fill in your own keys; never commit .env
uv run main.py             # FastAPI on :8000, Streamlit on :8501 (both local only)
```

Without uv: `pip install -r requirements.txt` on Python 3.14, then `python main.py`. `requirements.txt` is exported from `uv.lock` (`uv export --no-hashes --no-dev --no-emit-project -o requirements.txt`); regenerate it after changing dependencies.

Open http://localhost:8501. With no database connected the dashboard is empty: open the **Data** page and choose *Load mock data* to preview it. Mock data is fictional, labelled MOCK everywhere, and *Delete mock data* removes it again.

The active company comes from `ACTIVE_COMPANY` (a folder under `gitignore/data/`). To collect that company's public documents into its `kb/` folder:

```bash
uv run python -m app.backend.services.kb_scraper --company <Company>
```

Use a dev database, a dev bot and test accounts while developing. Nothing is sent to anyone without the owner's explicit approval.

```bash
uv run ruff check . && uv run ruff format .
uv run pytest app/tests
```

## Documentation

| File | What it covers |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, funnel, conversation flow, dashboard, providers |
| [`SCHEMA.md`](SCHEMA.md) / [`SCHEMA.sql`](SCHEMA.sql) | Database schema and the script that creates it in Supabase |
| [`docs/CHANNELS.md`](docs/CHANNELS.md) | Channel adapters (Gmail, Telegram) and how to add one |
| [`DECISIONS.md`](DECISIONS.md) | Design choices as "X over Y because Z" |
| [`SECURITY.md`](SECURITY.md) | Security model, reporting a vulnerability |
| [`CHANGELOG.md`](CHANGELOG.md) | Notable changes |
| [`CLAUDE.md`](CLAUDE.md) | Project rules and conventions for Claude Code |

## Notable dependencies and licenses

New dependencies must be license-compatible with Apache 2.0. Notable ones are listed here.

| Dependency | Purpose | License |
|---|---|---|
| FastAPI | HTTP API | MIT |
| Uvicorn | ASGI server | BSD-3-Clause |
| Streamlit | Dashboard | Apache-2.0 |
| httpx | Dashboard-to-API client | BSD-3-Clause |
| pydantic-settings | Settings | MIT |
| PyYAML | Company profile | MIT |
| pytest, ruff (dev) | Tests, lint and format | MIT |
| three.js r149 (vendored in `app/streamlit/components/`) | 3D orb | MIT |

The Ubuntu font is loaded from Google Fonts at view time and is not redistributed in this repository.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
