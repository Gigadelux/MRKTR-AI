"""Provider interfaces. The harness depends on these, never on a concrete adapter."""

from __future__ import annotations

from typing import Protocol


class EmailChannel(Protocol):
    async def send(self, *, to: str, subject: str, text: str, html: str | None = None) -> dict:
        """Send one email to an allowlisted recipient. Returns Gmail's ids (id, threadId)."""
        ...


class ChatChannel(Protocol):
    async def send_text(self, chat_id: int, text: str) -> list[int]: ...
    async def send_sticker(self, chat_id: int, file_id: str) -> int: ...
    async def send_voice(self, chat_id: int, audio: bytes, seconds: int | None = None) -> int: ...


class TTSProvider(Protocol):
    async def speak(self, text: str) -> bytes:
        """Text to speech. Returns audio the chat channel accepts (OGG/Opus)."""
        ...
