"""Telegram adapter (ChatChannel), sending only. Polling and /start come in a later step.

No default parse_mode: model text is plain text. With HTML mode a stray "<" or "<e:smile>"
makes Telegram reject the message, and model output could inject links or formatting.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BufferedInputFile

from app.backend.core.errors import ConfigError
from app.backend.core.settings import Settings

TEXT_LIMIT = 4096  # Telegram: 1-4096 characters per text message


def split_text(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    """Split on paragraph boundaries, then on spaces, so no part exceeds the limit."""
    parts: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            parts.append(current)
            current = ""
        while len(para) > limit:
            cut = para.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            parts.append(para[:cut])
            para = para[cut:].lstrip()
        current = para
    if current.strip():
        parts.append(current)
    return parts


async def send_with_retry[T](call: Callable[[], Awaitable[T]], attempts: int = 3) -> T:
    """Retry when Telegram answers 429, waiting as long as it asks."""
    for attempt in range(attempts):
        try:
            return await call()
        except TelegramRetryAfter as exc:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(exc.retry_after + 0.5)
    raise RuntimeError("unreachable")


class TelegramChannel:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send_text(self, chat_id: int, text: str) -> list[int]:
        ids: list[int] = []
        for i, part in enumerate(split_text(text)):
            if i:
                await asyncio.sleep(1)  # about 1 message per second per chat
            msg = await send_with_retry(lambda p=part: self.bot.send_message(chat_id, p))
            ids.append(msg.message_id)
        return ids

    async def send_sticker(self, chat_id: int, file_id: str) -> int:
        msg = await send_with_retry(lambda: self.bot.send_sticker(chat_id, file_id))
        return msg.message_id

    async def send_voice(self, chat_id: int, audio: bytes, seconds: int | None = None) -> int:
        await self.bot.send_chat_action(chat_id, ChatAction.RECORD_VOICE)
        voice = BufferedInputFile(audio, filename="voice.ogg")
        msg = await send_with_retry(lambda: self.bot.send_voice(chat_id, voice, duration=seconds))
        return msg.message_id


def make_bot(settings: Settings) -> Bot:
    if not settings.telegram_bot_token:
        raise ConfigError("TELEGRAM_BOT_TOKEN is not set. Create a dev bot with @BotFather.")
    return Bot(settings.telegram_bot_token)


async def get_bot_username(settings: Settings) -> str:
    """Check the bot token against Telegram (getMe) and return the bot's username."""
    bot = make_bot(settings)
    try:
        me = await bot.get_me()
    except Exception as exc:  # never include the token in the message
        raise ConfigError(f"Telegram rejected the bot token ({type(exc).__name__}).") from None
    finally:
        await bot.session.close()
    if not me.username:
        raise ConfigError("The Telegram bot has no username.")
    return me.username
