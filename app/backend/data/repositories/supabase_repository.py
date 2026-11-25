"""Supabase repository for the funnel: contacts to engage, start tokens, sends and tool calls.

Uses the service-role key (RLS bypass) and must point at the DEV project unless the owner
approved otherwise. The supabase client is synchronous, so calls run in a worker thread.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.backend.core.errors import ConfigError
from app.backend.core.settings import Settings
from app.backend.data.models.tables import Crm, User


@dataclass(frozen=True)
class Contact:
    user: User
    crm: Crm


class SupabaseRepository:
    def __init__(self, client: Any) -> None:
        self._db = client

    async def contacts_to_engage(self, company: str, limit: int | None = None) -> list[Contact]:
        """Leads of this company with an email and consent on record, not contacted yet."""

        def run() -> list[dict]:
            q = (
                self._db.table("users")
                .select("*, crm!inner(*)")
                .eq("company", company)
                .not_.is_("email", "null")
                .not_.is_("consent_at", "null")
                .eq("crm.status", "new")
                .order("created_at")
            )
            if limit:
                q = q.limit(limit)
            return q.execute().data

        contacts = []
        for row in await asyncio.to_thread(run):
            crm = row.pop("crm")
            crm = crm[0] if isinstance(crm, list) else crm
            contacts.append(Contact(user=User.model_validate(row), crm=Crm.model_validate(crm)))
        return contacts

    async def set_start_token(self, user_id: str, token: str) -> None:
        await asyncio.to_thread(
            lambda: (
                self._db.table("users")
                .update({"start_token": token})
                .eq("user_id", user_id)
                .execute()
            )
        )

    async def record_email_sent(self, user_id: str, gmail: dict, subject: str, text: str) -> None:
        """Outgoing email row + email_sent event + crm status 'contacted'."""

        def run() -> None:
            self._db.table("messages").insert(
                {
                    "user_id": user_id,
                    "channel": "email",
                    "channel_message_id": gmail.get("id"),
                    "direction": "out",
                    "message_type": "text",
                    "text": text,
                    "metadata": {
                        "gmail_thread_id": gmail.get("threadId"),
                        "rfc822_message_id": gmail.get("rfc822_message_id"),
                        "subject": subject,
                    },
                }
            ).execute()
            self._db.table("events").insert(
                {"user_id": user_id, "type": "email_sent", "payload": {"gmail_id": gmail.get("id")}}
            ).execute()
            self._db.table("crm").update(
                {"status": "contacted", "updated_at": datetime.now(UTC).isoformat()}
            ).eq("user_id", user_id).execute()

        await asyncio.to_thread(run)

    async def log_tool_call(
        self,
        user_id: str,
        tool: str,
        args: dict,
        result: dict | None,
        refused_reason: str | None,
    ) -> None:
        await asyncio.to_thread(
            lambda: (
                self._db.table("tool_calls")
                .insert(
                    {
                        "user_id": user_id,
                        "tool": tool,
                        "args": args,
                        "result": result,
                        "refused_reason": refused_reason,
                    }
                )
                .execute()
            )
        )


def make_repository(settings: Settings) -> SupabaseRepository:
    from supabase import create_client

    if not settings.supabase_url or not settings.supabase_key:
        raise ConfigError(
            "Supabase is not configured: set SUPABASE_URL and SUPABASE_KEY (dev project)."
        )
    return SupabaseRepository(create_client(settings.supabase_url, settings.supabase_key))
