"""Telegram seller agent: one turn of the conversation.

The LLM sees two tools: ``search_kb`` (answers come from the knowledge base) and
``send_voice_note`` (checked in code, see tools/audio_generator.py). Its final text may carry one
``<e:name>`` tag: the tag is stripped, the text is sent, then the matching sticker.
Bot polling, /start and mode buttons are wired in a later step; this module only needs a context.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from app.backend.harness.parsers.tags import parse_reply
from app.backend.harness.prompts.system_prompt import seller_system_prompt
from app.backend.harness.tools.audio_generator import send_voice_note
from app.backend.harness.tools.context import SellerContext
from app.backend.harness.tools.messaging import send_message, send_sticker
from app.backend.services.llm import LLM

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4
KB_RESULTS = 5

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "Search the company's public knowledge base. Use it before stating any product, pricing or capability fact.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look up"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_voice_note",
            "description": "Send a short voice note (under ~60 s, max 900 characters) with this exact text. At most one per reply. May be refused; then reply in text.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "What the voice says"}},
                "required": ["text"],
            },
        },
    },
]


def default_search(query: str, k: int) -> list[dict]:
    from app.backend.harness.RAG.mcp_rag import search

    return [hit.model_dump() for hit in search(query, k)]


async def run_tool(
    ctx: SellerContext, name: str, raw_args: str, search: Callable[[str, int], list[dict]]
) -> str:
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "arguments were not valid JSON"})
    if name == "search_kb":
        hits = await asyncio.to_thread(search, str(args.get("query", "")), KB_RESULTS)
        return json.dumps({"results": hits}, ensure_ascii=False)
    if name == "send_voice_note":
        result = await send_voice_note(ctx, str(args.get("text", "")))
        return result.model_dump_json()
    return json.dumps({"error": f"unknown tool {name}"})


async def respond(
    ctx: SellerContext,
    llm: LLM,
    history: list[dict[str, Any]],
    user_text: str,
    search: Callable[[str, int], list[dict]] = default_search,
) -> str:
    """Run one turn and send the reply. Returns the text that was sent (tags stripped).

    ``user_text`` must already be masked by the guards; ``history`` holds earlier turns as
    OpenAI chat messages.
    """
    ctx.new_turn()
    system = seller_system_prompt(
        ctx.company,
        ctx.crm,
        ctx.user.pref_mode,
        sorted(ctx.stickers),
        ctx.settings.company_dir / "prompts",
        first_message=not ctx.has_sent_text,
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": user_text},
    ]
    final = ""
    for round_ in range(MAX_TOOL_ROUNDS + 1):
        last = round_ == MAX_TOOL_ROUNDS
        resp = await llm.client.chat.completions.create(
            model=llm.model,
            messages=messages,
            tools=TOOLS,
            tool_choice="none" if last else "auto",
        )
        msg = resp.choices[0].message
        if not msg.tool_calls or last:
            final = msg.content or ""
            break
        messages.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls:
            output = await run_tool(ctx, call.function.name, call.function.arguments, search)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

    text, sticker = parse_reply(final, frozenset(ctx.stickers))
    await send_message(ctx, text)
    if sticker:
        await send_sticker(ctx, sticker)
    return text
