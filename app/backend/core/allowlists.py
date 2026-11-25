"""Allowlists, enforced in code. Neither the prompt nor the LLM can change them.

The email addresses themselves are personal data, so they live in the git-ignored
``gitignore/data/<company>/allowlist.yaml`` (``emails: [...]``); the checks live here.
"""

from __future__ import annotations

from email.utils import parseaddr

import yaml

from app.backend.core.settings import Settings
from app.backend.data.models.tables import User


class RecipientNotAllowed(Exception):
    """Raised before anything is sent."""


def load_email_allowlist(settings: Settings) -> frozenset[str]:
    path = settings.company_dir / "allowlist.yaml"
    if not path.is_file():
        return frozenset()  # empty allowlist: nothing can be sent
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return frozenset(str(e).strip().lower() for e in data.get("emails", []) if str(e).strip())


def plain_address(value: str) -> str:
    """Accept only a bare single address. Display names, lists and header tricks are rejected."""
    if any(c in value for c in "\r\n,;<>\"'"):
        raise RecipientNotAllowed("not a plain single address")
    addr = parseaddr(value)[1].lower()
    if not addr or "@" not in addr or addr != value.strip().lower():
        raise RecipientNotAllowed("not a plain single address")
    return addr


def check_recipient(value: str, allowed: frozenset[str]) -> str:
    addr = plain_address(value)
    if addr not in allowed:
        raise RecipientNotAllowed("recipient is not on the allowlist")
    return addr


def is_telegram_allowed(user: User) -> bool:
    """The bot talks only to users who redeemed a start token and have consent on record."""
    return user.channel_ids.get("telegram") is not None and user.consent_at is not None
