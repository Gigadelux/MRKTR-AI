# Channels

_Last updated: 2026-11-20_

A channel is how the agent talks to the outside world. Channels are **adapters**: each sits behind an interface in `app/backend/services/`, and the harness never imports a concrete adapter.

| Channel | Interface | Adapter | Role in the funnel | Setting |
|---|---|---|---|---|
| Email | `EmailChannel` | Gmail API | First touch, reply sorting, human-approved drafts | `GMAIL_CREDENTIALS_PATH` |
| Chat | `ChatChannel` | Telegram Bot API | The conversation: text, stickers, voice notes, inline buttons | `TELEGRAM_BOT_TOKEN` |

## Email (Gmail)

- **Outbound:** a short personalized first touch with a Telegram deep link (`t.me/<bot>?start=<token>`). The company disclaimer, when set, appears in every email.
- **Allowlist:** email goes only to recipients on the allowlist in `app/backend/core/`. A recipient outside it raises an error, whatever the prompt or the LLM says.
- **Inbound:** replies are sorted (for example interested / question / not now / unsubscribe) and answered with a draft. A human approves each draft before it is sent.
- **Approval:** no email is sent without the owner's explicit approval.

## Chat (Telegram)

- **Entry:** `/start <token>` links the email to the Telegram user. The bot checks the token and the consent record, discloses that it is an AI, and asks the user to pick a mode.
- **Modes:** *Audio + transcript*, *Audio only*, *Text only*, changeable with `/settings`. The mode is a hard limit enforced in code.
- **Allowlist:** the bot replies only to users who redeemed a valid token and have consent on record. Everyone else is ignored.
- **Incoming:** text goes through masking. Voice notes are transcribed first, and the transcript goes through the same masking.
- **Outgoing:** the agent chooses text, at most one sticker (`<e:name>` tag), or a voice note through the `send_voice_note` tool. Voice notes are converted to OGG/Opus.
- **Transcripts:** every message is saved with its source (`user_text`, `stt`, `agent_text`, `tts_script`).

## Adding a channel

Adding a channel means adding an adapter and a settings value, and nothing else:

1. Define or reuse the interface in `app/backend/services/` (`EmailChannel` or `ChatChannel`, or a new one if the capability is new).
2. Write the adapter in `app/backend/services/`. Keep the provider's quirks (formats, headers, limits) inside it.
3. Add the setting(s) to `app/backend/core/` and `example.env`, and register the adapter in the provider registry.
4. Enforce the same rules as the existing channels: allowlist, consent, masking before the LLM, a transcript for every message, and no outbound action without approval.
5. Check the provider's capabilities at startup and fail with a clear message instead of degrading silently.
6. Add unit tests in `app/tests/`.

WhatsApp is an example of a future channel that would follow this same pattern.
