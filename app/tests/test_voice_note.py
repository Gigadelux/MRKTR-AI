import asyncio

import pytest

from app.backend.harness.tools.audio_generator import MAX_VOICE_CHARS, send_voice_note
from app.backend.harness.tools.context import SellerContext
from app.tests.conftest import make_crm, make_user
from app.tests.fakes import FakeChat, FakeLog, FakeTTS


async def safe(_: str) -> bool:
    return True


async def unsafe(_: str) -> bool:
    return False


def make_ctx(
    settings, company, *, guard=safe, tts=None, has_sent_text=True, **user_kw
) -> SellerContext:
    return SellerContext(
        settings=settings,
        company=company,
        user=make_user(**user_kw),
        crm=make_crm(),
        chat=FakeChat(),
        tts=tts if tts is not None else FakeTTS(),
        repo=FakeLog(),
        stickers={},
        guard=guard,
        has_sent_text=has_sent_text,
    )


def run(ctx, text="Hi, this is a short voice note."):
    return asyncio.run(send_voice_note(ctx, text))


@pytest.mark.parametrize(
    ("user_kw", "guard", "reason"),
    [
        ({"consent_at": None}, safe, "not_allowlisted"),
        ({"pref_mode": "text_only"}, safe, "text_only_mode"),
        ({}, None, "no_content_guard"),
        ({}, unsafe, "unsafe_content"),
    ],
)
def test_refusals_before_tts(settings, company, user_kw, guard, reason):
    ctx = make_ctx(settings, company, guard=guard, **user_kw)
    result = run(ctx)
    assert (result.sent, result.refused_reason) == (False, reason)
    assert ctx.tts.calls == [] and ctx.chat.sent == []
    assert ctx.repo.calls == [
        {"tool": "send_voice_note", "args": {"chars": 31}, "refused_reason": reason}
    ]


def test_first_message_must_be_text(settings, company):
    ctx = make_ctx(settings, company, has_sent_text=False)
    result = run(ctx)
    assert result.refused_reason == "first_message_text"
    assert ctx.tts.calls == [] and ctx.chat.sent == []


def test_text_only_wins_over_missing_guard(settings, company):
    ctx = make_ctx(settings, company, guard=None, pref_mode="text_only")
    assert run(ctx).refused_reason == "text_only_mode"


def test_dev_flag_allows_unguarded_voice(settings, company):
    settings.dev_allow_unguarded_voice = True
    assert run(make_ctx(settings, company, guard=None)).sent


def test_too_long(settings, company):
    ctx = make_ctx(settings, company)
    assert run(ctx, "a" * (MAX_VOICE_CHARS + 1)).refused_reason == "too_long"


def test_rate_limits(settings, company):
    ctx = make_ctx(settings, company)
    assert run(ctx).sent
    assert run(ctx).refused_reason == "rate_limit_turn"
    ctx.new_turn()
    ctx.voice_notes_total = settings.max_voice_notes_per_conversation
    assert run(ctx).refused_reason == "rate_limit_conversation"


def test_success_sends_voice_and_transcript(settings, company):
    ctx = make_ctx(settings, company)
    result = run(ctx, "Hello!")
    assert result.sent and result.refused_reason is None
    assert [kind for kind, _, _ in ctx.chat.sent] == ["voice", "text"]
    assert ctx.chat.sent[1][2] == "Hello!"


def test_audio_only_sends_no_transcript(settings, company):
    ctx = make_ctx(settings, company, pref_mode="audio_only")
    run(ctx)
    assert [kind for kind, _, _ in ctx.chat.sent] == ["voice"]


def test_tts_failure_is_reported_and_logged(settings, company):
    ctx = make_ctx(settings, company, tts=FakeTTS(fail=True))
    result = run(ctx)
    assert result.refused_reason == "tts_failed"
    assert ctx.chat.sent == []
    assert ctx.repo.calls[0]["refused_reason"] == "tts_failed"
