# Security Policy

_Last updated: 2026-11-25_

## Supported versions

| Version | Supported |
|---|---|
| `main` (pre-release) | Yes |

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's **private vulnerability reporting** (Security tab → "Report a vulnerability") on this repository. Include what you found, how to reproduce it, and the impact you expect. Never include real personal data or live credentials in a report.

## Security model

- **Allowlists live in code** (`app/backend/core/`). Email goes only to allowlisted recipients. The Telegram bot replies only to users who redeemed a valid start token and have consent on record. Neither the prompt nor the LLM can change them.
- **No outbound action without explicit approval** from the owner. Development defaults to a dev database, a dev bot and test accounts.
- **Prompt-injection masking:** incoming text is split into sentences, each scored by an injection guard and a content guard. Flagged sentences are replaced before the LLM sees them. Originals are stored only in `masked_messages` (row-level security, owner only) and never logged elsewhere.
- **Email allowlist:** the checks live in `app/backend/core/allowlists.py`; the addresses (personal data) live in the git-ignored `gitignore/data/<company>/allowlist.yaml`. Only a bare single address is accepted (no display names, lists, Cc/Bcc or header tricks), and the Gmail adapter re-checks it while building each message. No file means nothing can be sent.
- **Outreach gate:** the engager is a dry run by default (HTML previews in `gitignore/temp/outbox/`). Sending needs `--send` plus typing `SEND` in a terminal. LLM-written email text is HTML-escaped, so it cannot add markup or links.
- **Voice notes** are produced only through the `send_voice_note` tool. In order, it checks: allowlist and consent, the user's `/settings` limit (*Text only* blocks audio), that a text was already sent (the first message is always text), the content guard, maximum length, rate limits. Which medium to use is otherwise the agent's choice, or the user's when they ask in the chat; that request is followed through the prompt only. Only then does it run text-to-speech, send and log. Refusals are logged too. **No content guard exists yet**, so voice notes are refused (`no_content_guard`) unless `DEV_ALLOW_UNGUARDED_VOICE=true`, which is for the dev bot only.
- **Local-only dashboard:** the API and the Streamlit dashboard bind to `127.0.0.1`. The dashboard shows lead data and has no login, so it must not be exposed to a network.
- **Mock data is labelled:** fictional data is always flagged MOCK in the API and the UI, and deleting it removes only the files the generator wrote.
- **AI disclosure:** the agent says it is an AI on first contact, and the company disclaimer is always shown when set.
- **Secrets and private data:** `.env`, keys, tokens, CRM data, knowledge-base content and real-company prompts are never committed. `gitignore/` is ignored by git, and a secret scan (for example gitleaks) runs in the pre-push hook.
- **Personal data:** only what the funnel needs is collected, with consent. Voice audio (incoming or generated) is never stored, not even as a Telegram `file_id`; only its transcript is kept. A user and everything linked to them can be deleted.
- **Evals:** security suites track masking precision/recall, injection success after masking, benign-decoy hijack rate, unsafe-content rate, PII leaks, blocked recipient redirects, and replies to non-allowlisted users (must be 0). A failing eval is fixed in the code, never by changing the test, its threshold or its dataset.

## Security-relevant changes

Record changes to allowlists, guards, masking, auth and data retention here, newest first.

| Date | Change | Area |
|---|---|---|
| 2026-11-25 | Medium chosen by the agent per reply; `/settings` *Text only* stays the code-enforced block; voice notes refused before the first text (`first_message_text`) | Guards |
| 2026-11-25 | Email allowlist (`core/allowlists.py` + git-ignored `allowlist.yaml`), checked again inside the Gmail adapter; engager dry run by default, `--send` needs typed confirmation | Allowlist, outbound approval |
| 2026-11-25 | `send_voice_note` checks in code; refused by default until a content guard exists (`DEV_ALLOW_UNGUARDED_VOICE` for dev only) | Guards |
| 2026-11-25 | Knowledge-base scraper removed; the RAG index (Milvus Lite) is a local file in `gitignore/temp/rag/` | Data retention |
| 2026-11-24 | `messages.audio_ref` removed: voice audio is never stored, only its transcript | Data retention |
| 2026-11-24 | A Telegram id can be linked to only one user (unique index), so two leads cannot share one account | Allowlist integrity |
| 2026-11-20 | Database schema with row-level security on every table and no policies (service role only); `masked_messages` unreachable by other roles | Data access |
| 2026-11-20 | Dashboard and API bound to `127.0.0.1` | Network exposure |
| 2026-11-20 | Collected public knowledge-base content lives only in `gitignore/` | Data retention |
