"""send_voice_note: the ONLY path from model output to text-to-speech (hard rule 5).

Checks run in code, in this order, and every call is logged (refusals included):
1. user is allowlisted (redeemed start token + consent);
2. the user's /settings limit allows audio (text_only -> refused);
3. the agent already sent a text in this conversation (the first message is always text);
4. the content guard passes. No guard exists yet: refused unless DEV_ALLOW_UNGUARDED_VOICE;
5. the text fits the length budget (~60 s of speech);
6. rate limit: at most 1 per turn and MAX_VOICE_NOTES_PER_CONVERSATION per conversation.
Then: TTS -> OGG/Opus -> send -> transcript as a separate message in audio_transcript mode.
Which medium to use is the agent's choice (or the user's, when they ask in the chat); these checks
are the hard limits around that choice.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from app.backend.core.allowlists import is_telegram_allowed
from app.backend.harness.tools.context import SellerContext

log = logging.getLogger(__name__)

MAX_VOICE_CHARS = 900  # rough budget for ~60 s of speech; measure and tune
SECONDS_PER_CHAR = 1 / 15  # rough estimate for the duration Telegram shows


class VoiceNoteResult(BaseModel):
    sent: bool
    refused_reason: str | None = None
    message: str  # short text the agent reads


def _check(ctx: SellerContext) -> str | None:
    if not is_telegram_allowed(ctx.user):
        return "not_allowlisted"
    if ctx.user.pref_mode == "text_only":
        return "text_only_mode"
    if not ctx.has_sent_text:
        return "first_message_text"
    if ctx.guard is None and not ctx.settings.dev_allow_unguarded_voice:
        return "no_content_guard"
    return None


def _check_limits(ctx: SellerContext, text: str) -> str | None:
    if not text.strip():
        return "empty_text"
    if len(text) > MAX_VOICE_CHARS:
        return "too_long"
    if ctx.voice_notes_this_turn >= 1:
        return "rate_limit_turn"
    if ctx.voice_notes_total >= ctx.settings.max_voice_notes_per_conversation:
        return "rate_limit_conversation"
    return None


REFUSAL_MESSAGES = {
    "not_allowlisted": "Voice notes are not available for this user.",
    "text_only_mode": "The user chose text only. Reply in text.",
    "first_message_text": "The first message of a conversation must be text. Reply in text.",
    "no_content_guard": "Voice notes are disabled right now. Reply in text.",
    "unsafe_content": "That text can't be sent as audio. Reply in text.",
    "empty_text": "The voice note text was empty.",
    "too_long": f"Too long for a voice note (max {MAX_VOICE_CHARS} characters). Shorten it or reply in text.",
    "rate_limit_turn": "Only one voice note per reply. Continue in text.",
    "rate_limit_conversation": "Voice note limit for this conversation reached. Continue in text.",
    "tts_unavailable": "Voice notes are not configured. Reply in text.",
    "tts_failed": "The voice note could not be generated. Reply in text.",
}


async def send_voice_note(ctx: SellerContext, text: str) -> VoiceNoteResult:
    reason = _check(ctx)
    if reason is None and ctx.guard is not None and not await ctx.guard(text):
        reason = "unsafe_content"
    reason = reason or _check_limits(ctx, text)
    if reason is None and ctx.tts is None:
        reason = "tts_unavailable"

    result: VoiceNoteResult
    if reason is None:
        ctx.voice_notes_this_turn += (
            1  # counted on attempt, so a failing TTS can't be retried in a loop
        )
        ctx.voice_notes_total += 1
        try:
            audio = await ctx.tts.speak(text)  # type: ignore[union-attr]
        except Exception as exc:
            log.warning("voice note TTS failed: %s", type(exc).__name__)
            reason = "tts_failed"
        else:
            seconds = max(1, round(len(text) * SECONDS_PER_CHAR))
            ctx.sent_ids.append(await ctx.chat.send_voice(ctx.chat_id, audio, seconds))
            if ctx.user.pref_mode == "audio_transcript":
                ctx.sent_ids.extend(await ctx.chat.send_text(ctx.chat_id, text))
            result = VoiceNoteResult(sent=True, message="Voice note sent.")

    if reason is not None:
        result = VoiceNoteResult(
            sent=False, refused_reason=reason, message=REFUSAL_MESSAGES[reason]
        )
    await ctx.repo.log_tool_call(
        ctx.user.user_id,
        "send_voice_note",
        {"chars": len(text)},  # length only: tool_calls must not duplicate message text
        result.model_dump(),
        result.refused_reason,
    )
    return result
