import asyncio
import json

import pytest

from app.backend.core.errors import ConfigError
from app.backend.data.repositories.supabase_repository import Contact
from app.backend.harness.agents import engager
from app.backend.harness.prompts.engager_prompt import engager_prompt
from app.backend.services.telegram import get_bot_username
from app.tests.conftest import make_crm, make_user
from app.tests.fakes import FakeLLM, reply


def draft(body="Hi Beta Corp team.\n\nWe <b>help</b> with rockets.", subject="Rockets for Beta"):
    return engager.EmailDraft(subject=subject, body=body)


def test_render_escapes_model_text_and_has_required_parts(company):
    text, html = engager.render_email(company, draft(), "https://t.me/acme_bot?start=TOKEN")
    assert "&lt;b&gt;help&lt;/b&gt;" in html and "<b>help</b>" not in html
    assert 'href="https://t.me/acme_bot?start=TOKEN"' in html
    assert "Fictional demo company." in html and "Fictional demo company." in text
    assert "written and sent by an AI" in html and "AI assistant" in text
    assert 'Reply "stop"' in text and "Reply &quot;stop&quot;" in html
    assert "$" not in html  # every placeholder was filled


def test_parse_draft_tolerates_fences_and_rejects_bad_output():
    raw = '```json\n{"subject": "Hi", "body": "Hello"}\n```'
    assert engager.parse_draft(raw).subject == "Hi"
    with pytest.raises(ValueError):
        engager.parse_draft("no json here")
    with pytest.raises(ValueError):
        engager.parse_draft('{"subject": "Hi\\nBcc: x", "body": "b"}')


def test_prompt_is_personalized(company):
    prompt = engager_prompt(company, make_crm(industry="Aerospace"))
    assert "Beta Corp" in prompt and "CTO" in prompt and "Aerospace" in prompt
    assert "$" not in prompt


def test_prepare_and_dry_run_write_previews_without_sending(settings, company):
    contact = Contact(user=make_user(), crm=make_crm())
    llm = FakeLLM([reply(content=json.dumps({"subject": "Hello Beta", "body": "Short note."}))])
    emails = asyncio.run(engager.prepare(settings, company, llm, "acme_bot", [contact]))
    assert len(emails[0].token) == 43
    assert f"https://t.me/acme_bot?start={emails[0].token}" in emails[0].text
    paths = engager.write_previews(settings, emails)
    assert paths[0].parent == settings.outbox_dir and paths[0].read_text().startswith("<!DOCTYPE")


def test_existing_start_token_is_reused(settings, company):
    contact = Contact(user=make_user(start_token="KEEP"), crm=make_crm())
    llm = FakeLLM([reply(content='{"subject": "s", "body": "b"}')])
    emails = asyncio.run(engager.prepare(settings, company, llm, "bot", [contact]))
    assert emails[0].token == "KEEP"


def test_send_all_saves_token_then_records(company):
    calls = []

    class Repo:
        async def set_start_token(self, user_id, token):
            calls.append(("token", user_id, token))

        async def record_email_sent(self, user_id, gmail, subject, text):
            calls.append(("recorded", user_id, gmail["id"]))

    class Gmail:
        async def send(self, *, to, subject, text, html=None):
            calls.append(("sent", to))
            return {"id": "g1", "threadId": "t1"}

    out = engager.Outgoing(Contact(make_user(), make_crm()), "TOK", "s", "t", "<html>")
    assert asyncio.run(engager.send_all(Repo(), Gmail(), [out])) == 1
    assert calls == [
        ("token", "u1", "TOK"),
        ("sent", "friend@example.com"),
        ("recorded", "u1", "g1"),
    ]


def test_confirm_refuses_without_a_terminal(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert engager.confirm(1) is False


def test_missing_bot_token_is_a_clear_error(settings):
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        asyncio.run(get_bot_username(settings))
