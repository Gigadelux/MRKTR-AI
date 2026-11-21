# Security Policy

_Last updated: 2026-11-20_

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
- **Voice notes** are produced only through the `send_voice_note` tool. In order, it checks: allowlist and consent, the user's mode, the content guard, maximum length, rate limits. Only then does it run text-to-speech, send and log. Refusals are logged too.
- **Local-only dashboard:** the API and the Streamlit dashboard bind to `127.0.0.1`. The dashboard shows lead data and has no login, so it must not be exposed to a network.
- **Mock data is labelled:** fictional data is always flagged MOCK in the API and the UI, and deleting it removes only the files the generator wrote.
- **AI disclosure:** the agent says it is an AI on first contact, and the company disclaimer is always shown when set.
- **Secrets and private data:** `.env`, keys, tokens, CRM data, knowledge-base content and real-company prompts are never committed. `gitignore/` is ignored by git, and a secret scan (for example gitleaks) runs in the pre-push hook.
- **Personal data:** only what the funnel needs is collected, with consent. A user and everything linked to them can be deleted.
- **Evals:** security suites track masking precision/recall, injection success after masking, benign-decoy hijack rate, unsafe-content rate, PII leaks, blocked recipient redirects, and replies to non-allowlisted users (must be 0). A failing eval is fixed in the code, never by changing the test, its threshold or its dataset.

## Security-relevant changes

Record changes to allowlists, guards, masking, auth and data retention here, newest first.

| Date | Change | Area |
|---|---|---|
| 2026-11-20 | Database schema with row-level security on every table and no policies (service role only); `masked_messages` unreachable by other roles | Data access |
| 2026-11-20 | Dashboard and API bound to `127.0.0.1` | Network exposure |
| 2026-11-20 | Collected public knowledge-base content lives only in `gitignore/` | Data retention |
