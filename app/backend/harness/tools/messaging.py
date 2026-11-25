"""Text and sticker sending for the seller. Both refuse users who are not allowlisted."""

from __future__ import annotations

import logging

from app.backend.core.allowlists import is_telegram_allowed
from app.backend.harness.tools.context import SellerContext

log = logging.getLogger(__name__)


async def send_message(ctx: SellerContext, text: str) -> list[int]:
    if not is_telegram_allowed(ctx.user) or not text.strip():
        return []
    ids = await ctx.chat.send_text(ctx.chat_id, text)
    ctx.sent_ids.extend(ids)
    ctx.has_sent_text = True
    return ids


async def send_sticker(ctx: SellerContext, name: str) -> int | None:
    """Send the sticker for an expression name. Unknown names send nothing."""
    file_id = ctx.stickers.get(name)
    if not file_id or not is_telegram_allowed(ctx.user):
        return None
    msg_id = await ctx.chat.send_sticker(ctx.chat_id, file_id)
    ctx.sent_ids.append(msg_id)
    return msg_id
