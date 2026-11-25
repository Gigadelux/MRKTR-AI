"""Per-conversation context passed to the seller's tools. Built by code, never by the LLM."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

from app.backend.core.company import CompanyProfile
from app.backend.core.settings import Settings
from app.backend.data.models.tables import Crm, User
from app.backend.services.interfaces import ChatChannel, TTSProvider

# A content guard returns True when the text is safe. None = no guard configured.
ContentGuard = Callable[[str], Awaitable[bool]]


class ToolLog(Protocol):
    async def log_tool_call(
        self, user_id: str, tool: str, args: dict, result: dict | None, refused_reason: str | None
    ) -> None: ...


@dataclass
class SellerContext:
    settings: Settings
    company: CompanyProfile
    user: User
    crm: Crm | None
    chat: ChatChannel
    tts: TTSProvider | None
    repo: ToolLog
    stickers: dict[str, str]  # expression name -> Telegram file_id (stickers.yaml)
    guard: ContentGuard | None = None
    voice_notes_this_turn: int = 0
    voice_notes_total: int = 0  # for this conversation; the caller persists it between turns
    # True once the agent has sent a text in this conversation (the caller persists it).
    # The first message must be text, so voice notes are refused until then.
    has_sent_text: bool = False
    sent_ids: list[int] = field(default_factory=list)

    @property
    def chat_id(self) -> int:
        return int(self.user.channel_ids["telegram"])

    def new_turn(self) -> None:
        self.voice_notes_this_turn = 0
