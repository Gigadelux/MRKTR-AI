import asyncio
import json

from app.backend.harness.agents.seller import respond
from app.backend.harness.prompts.system_prompt import seller_system_prompt
from app.backend.harness.tools.context import SellerContext
from app.tests.conftest import make_crm, make_user
from app.tests.fakes import FakeChat, FakeLLM, FakeLog, FakeTTS, reply, tool_call


def make_ctx(settings, company, has_sent_text=True, **user_kw):
    return SellerContext(
        settings=settings,
        company=company,
        user=make_user(**user_kw),
        crm=make_crm(),
        chat=FakeChat(),
        tts=FakeTTS(),
        repo=FakeLog(),
        stickers={"smile": "FILE_SMILE"},
        has_sent_text=has_sent_text,
    )


def test_turn_with_kb_search_text_and_sticker(settings, company):
    ctx = make_ctx(settings, company)
    llm = FakeLLM(
        [
            reply(tool_calls=[tool_call("c1", "search_kb", json.dumps({"query": "rocket"}))]),
            reply(content="<e:smile> The Rocket is fictional (as of 2026-11-20)."),
        ]
    )
    queries = []

    def search(query, k):
        queries.append(query)
        return [{"source": "a.md", "collected_at": "2026-11-20", "text": "Rocket", "score": 1.0}]

    text = asyncio.run(respond(ctx, llm, [], "What is the Rocket?", search=search))
    assert text == "The Rocket is fictional (as of 2026-11-20)."
    assert queries == ["rocket"]
    assert ctx.chat.sent == [("text", 42, text), ("sticker", 42, "FILE_SMILE")]
    tool_msg = llm.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and "Rocket" in tool_msg["content"]


def test_voice_tool_refusal_reaches_the_model(settings, company):
    ctx = make_ctx(settings, company, pref_mode="text_only")
    llm = FakeLLM(
        [
            reply(tool_calls=[tool_call("c1", "send_voice_note", json.dumps({"text": "Hi"}))]),
            reply(content="Sure, in text then."),
        ]
    )
    asyncio.run(respond(ctx, llm, [], "Send me audio", search=lambda q, k: []))
    assert "text_only_mode" in llm.requests[1]["messages"][-1]["content"]
    assert ctx.tts.calls == []
    assert ctx.chat.sent == [("text", 42, "Sure, in text then.")]


def test_first_turn_is_text_even_if_the_model_asks_for_audio(settings, company):
    settings.dev_allow_unguarded_voice = True
    ctx = make_ctx(settings, company, has_sent_text=False)
    llm = FakeLLM(
        [
            reply(tool_calls=[tool_call("c1", "send_voice_note", json.dumps({"text": "Hi!"}))]),
            reply(content="Hi! I'm Robo, an AI assistant."),
        ]
    )
    asyncio.run(respond(ctx, llm, [], "hello", search=lambda q, k: []))
    system = llm.requests[0]["messages"][0]["content"]
    assert "This is your first message in this conversation: reply in text only." in system
    assert "first_message_text" in llm.requests[1]["messages"][-1]["content"]
    assert ctx.tts.calls == []
    assert ctx.chat.sent == [("text", 42, "Hi! I'm Robo, an AI assistant.")]
    assert ctx.has_sent_text  # from the next turn on, voice notes are possible


def test_tool_rounds_are_capped(settings, company):
    ctx = make_ctx(settings, company)
    loop = reply(tool_calls=[tool_call("c", "search_kb", '{"query": "x"}')])
    llm = FakeLLM([loop] * 4 + [reply(content="Done.")])
    asyncio.run(respond(ctx, llm, [], "hi", search=lambda q, k: []))
    assert len(llm.requests) == 5
    assert llm.requests[-1]["tool_choice"] == "none"


def test_prompt_reflects_profile(company):
    prompt = seller_system_prompt(company, make_crm(), None, ["smile"])
    assert "Robo" in prompt and "Acme" in prompt and "Fictional demo company." in prompt
    assert "What are you launching?" in prompt and "Beta Corp" in prompt
    assert "always plain text, never a voice note" in prompt
    assert "This is your first message" not in prompt
    assert "$" not in prompt  # every placeholder was filled


def test_prompt_medium_rules():
    from app.backend.harness.prompts.system_prompt import medium_rules

    chooses = medium_rules(None)
    assert "You choose the medium of every reply" in chooses
    assert "The lead decides only if they ask for a medium in the chat" in chooses
    assert "transcript" not in chooses
    assert "a transcript is sent after each voice note" in medium_rules("audio_transcript")
    assert "no transcript" in medium_rules("audio_only")
    text_only = medium_rules("text_only")
    assert "do not call `send_voice_note`" in text_only and "/settings" in text_only


def test_company_prompt_override(settings, company):
    prompts = settings.company_dir / "prompts"
    prompts.mkdir()
    (prompts / "seller.md").write_text("Custom for $company_name")
    assert seller_system_prompt(company, None, None, [], prompts) == "Custom for Acme"
