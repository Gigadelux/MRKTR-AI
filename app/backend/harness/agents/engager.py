"""First-touch outreach: a personalized email with the Telegram deep link.

    uv run python -m app.backend.harness.agents.engager            # dry run: writes previews only
    uv run python -m app.backend.harness.agents.engager --send     # asks for confirmation, then sends

Workflow:
1. Check the Telegram bot token (getMe) and get the bot username for the deep link.
2. Load leads to engage from the database (consent on record, email set, crm status 'new').
3. For each lead: start token -> LLM subject + body from the lead's crm profile -> HTML email.
4. Dry run (default): write previews to gitignore/temp/outbox/. Nothing is sent or saved.
   --send: confirm, send through the allowlisted Gmail channel, record message + event + status.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import logging
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from string import Template

from pydantic import BaseModel, Field, ValidationError

from app.backend.core.company import CompanyProfile, load_company
from app.backend.core.errors import ConfigError
from app.backend.core.settings import ROOT, Settings, get_settings
from app.backend.data.repositories.supabase_repository import Contact
from app.backend.harness.prompts.engager_prompt import engager_prompt
from app.backend.services.interfaces import EmailChannel
from app.backend.services.llm import LLM

log = logging.getLogger(__name__)

TEMPLATE_PATH = ROOT / "app" / "backend" / "data" / "assets" / "outreach_email.html"
P_STYLE = "margin:0 0 18px;"
UNSUBSCRIBE = 'Not interested? Reply "stop" and you won\'t get another email from us.'


class EmailDraft(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1500)


@dataclass(frozen=True)
class Outgoing:
    contact: Contact
    token: str
    subject: str
    text: str
    html: str


def deep_link(bot_username: str, token: str) -> str:
    return f"https://t.me/{bot_username}?start={token}"


def parse_draft(raw: str) -> EmailDraft:
    """The model must return a JSON object; tolerate code fences around it."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("LLM reply has no JSON object")
    draft = EmailDraft.model_validate(json.loads(match.group(0)))
    if "\n" in draft.subject or "\r" in draft.subject:
        raise ValueError("subject contains a newline")
    return draft


async def write_draft(
    llm: LLM, company: CompanyProfile, contact: Contact, prompts_dir: Path
) -> EmailDraft:
    prompt = engager_prompt(company, contact.crm, prompts_dir)
    for attempt in range(2):
        resp = await llm.client.chat.completions.create(
            model=llm.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        try:
            return parse_draft(resp.choices[0].message.content or "")
        except ValueError, ValidationError:
            if attempt == 1:
                raise
    raise RuntimeError("unreachable")


def render_email(company: CompanyProfile, draft: EmailDraft, link: str) -> tuple[str, str]:
    """Return (plain text, HTML). Model text is escaped: it can never inject markup or links."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", draft.body) if p.strip()]
    body_html = "\n".join(
        f'<p style="{P_STYLE}">{html.escape(p).replace(chr(10), "<br>")}</p>' for p in paragraphs
    )
    persona = company.persona.name
    disclaimer = company.disclaimer.strip()
    rendered = Template(TEMPLATE_PATH.read_text(encoding="utf-8")).substitute(
        lang=html.escape((company.persona.languages or ["en"])[0]),
        subject=html.escape(draft.subject),
        preheader=html.escape(paragraphs[0][:140] if paragraphs else draft.subject),
        persona_name=html.escape(persona),
        company_name=html.escape(company.name),
        body_html=body_html,
        bubble_text=html.escape(
            f"Hi, I'm {persona}, an AI assistant. Ask me anything about {company.name} "
            "in Telegram, by text or voice."
        ),
        cta_url=html.escape(link, quote=True),
        disclaimer_html=(
            f'<p style="margin:0 0 8px;">{html.escape(disclaimer)}</p>' if disclaimer else ""
        ),
        unsubscribe_text=html.escape(UNSUBSCRIBE),
    )
    text_parts = [
        "\n\n".join(paragraphs),
        f"{persona}\nAI assistant for {company.name}",
        f"Continue on Telegram: {link}",
        disclaimer,
        "This email was written and sent by an AI assistant.",
        UNSUBSCRIBE,
    ]
    return "\n\n".join(p for p in text_parts if p), rendered


async def prepare(
    settings: Settings,
    company: CompanyProfile,
    llm: LLM,
    bot_username: str,
    contacts: list[Contact],
) -> list[Outgoing]:
    out = []
    for contact in contacts:
        token = contact.user.start_token or secrets.token_urlsafe(32)  # 43 chars, deep-link safe
        draft = await write_draft(llm, company, contact, settings.company_dir / "prompts")
        text, rendered = render_email(company, draft, deep_link(bot_username, token))
        out.append(Outgoing(contact, token, draft.subject, text, rendered))
    return out


def write_previews(settings: Settings, emails: list[Outgoing]) -> list[Path]:
    settings.outbox_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for e in emails:
        path = settings.outbox_dir / f"{e.contact.user.user_id}.html"
        path.write_text(e.html, encoding="utf-8")
        paths.append(path)
    return paths


async def send_all(repo, gmail: EmailChannel, emails: list[Outgoing]) -> int:
    sent = 0
    for e in emails:
        if not e.contact.user.email:
            continue
        if e.contact.user.start_token != e.token:
            await repo.set_start_token(e.contact.user.user_id, e.token)
        result = await gmail.send(
            to=e.contact.user.email, subject=e.subject, text=e.text, html=e.html
        )
        await repo.record_email_sent(e.contact.user.user_id, result, e.subject, e.text)
        log.info("email sent to user %s", e.contact.user.user_id)  # never log the address
        sent += 1
    return sent


def confirm(count: int) -> bool:
    """Hard rule 3: no outbound action without the owner's explicit approval."""
    if not sys.stdin.isatty():
        return False
    answer = input(f"Send {count} email(s) to allowlisted recipients? Type SEND to confirm: ")
    return answer.strip() == "SEND"


async def run(send: bool, limit: int | None) -> int:
    from app.backend.core.allowlists import load_email_allowlist
    from app.backend.data.repositories.supabase_repository import make_repository
    from app.backend.services.gmail import make_gmail
    from app.backend.services.llm import make_llm
    from app.backend.services.telegram import get_bot_username

    settings = get_settings()
    company = load_company(settings)
    bot_username = await get_bot_username(settings)  # 1. is the bot token available and valid?
    llm = make_llm(settings)
    repo = make_repository(settings)
    contacts = await repo.contacts_to_engage(settings.active_company, limit)
    if not contacts:
        print("No leads to engage (need email, consent and crm status 'new').")
        return 0

    emails = await prepare(settings, company, llm, bot_username, contacts)
    for path, e in zip(write_previews(settings, emails), emails, strict=True):
        print(f"- {e.contact.user.user_id}: {e.subject!r} -> {path}")
    if not send:
        print("Dry run: nothing sent, no token saved. Open the previews, then re-run with --send.")
        return 0

    allowed = load_email_allowlist(settings)
    emails = [e for e in emails if (e.contact.user.email or "").lower() in allowed]
    if not emails:
        print("None of these leads is on the email allowlist (allowlist.yaml). Nothing sent.")
        return 1
    if not confirm(len(emails)):
        print("Not confirmed. Nothing sent.")
        return 1
    sent = await send_all(repo, make_gmail(settings, allowed), emails)
    print(f"Sent {sent} email(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send first-touch outreach emails.")
    parser.add_argument(
        "--send", action="store_true", help="send after confirmation (default: dry run)"
    )
    parser.add_argument("--limit", type=int, default=None, help="at most N leads")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        return asyncio.run(run(args.send, args.limit))
    except ConfigError as exc:
        print(f"Cannot run the engager: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
