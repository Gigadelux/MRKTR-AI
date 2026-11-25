"""Gmail adapter (EmailChannel). Sending only; the allowlist is checked inside build_raw.

One-time, interactive authorization (opens a browser, never run inside the server):
    uv run python -m app.backend.services.gmail authorize
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
import threading
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Any

from app.backend.core.allowlists import check_recipient
from app.backend.core.errors import ConfigError
from app.backend.core.settings import Settings, get_settings

# Narrowest scopes for the funnel: send first touches and approved replies, read incoming replies.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def token_path(client_secret: Path) -> Path:
    return client_secret.with_name("gmail_token.json")


def authorize(client_secret: Path) -> None:
    """Interactive OAuth flow. Writes the token next to the client file with 0600 permissions."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0)
    token = token_path(client_secret)
    token.write_text(creds.to_json())
    os.chmod(token, 0o600)  # the refresh token is a long-lived secret


def load_credentials(client_secret: Path) -> Any:
    """Non-interactive: load and refresh the token, or stop with a clear message."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token = token_path(client_secret)
    if not token.is_file():
        raise ConfigError(
            "No Gmail token: run `uv run python -m app.backend.services.gmail authorize`."
        )
    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds.valid:
        try:
            creds.refresh(Request())
        except RefreshError as exc:  # revoked, or expired (7 days while the app is in Testing)
            raise ConfigError("Gmail token expired: re-run the Gmail authorization.") from exc
    return creds


class GmailChannel:
    def __init__(self, service: Any, sender: str, allowed: frozenset[str]) -> None:
        self._service = service
        self._sender = sender
        self._allowed = allowed
        self._lock = threading.Lock()  # googleapiclient services are not thread-safe

    def build_raw(
        self, *, to: str, subject: str, text: str, html: str | None = None, message_id: str = ""
    ) -> str:
        recipient = check_recipient(to, self._allowed)  # raises before anything is built
        msg = EmailMessage()  # raises ValueError if a header contains a newline
        msg["To"] = recipient  # never Cc or Bcc
        msg["From"] = self._sender
        msg["Subject"] = subject
        msg["Message-ID"] = message_id or make_msgid()
        msg.set_content(text)
        if html:
            msg.add_alternative(html, subtype="html")
        return base64.urlsafe_b64encode(msg.as_bytes()).decode()

    def _send(self, **kwargs: Any) -> dict:
        message_id = make_msgid()  # RFC 822 id, kept so replies can be threaded later
        body = {"raw": self.build_raw(**kwargs, message_id=message_id)}
        with self._lock:
            sent = (
                self._service.users().messages().send(userId="me", body=body).execute(num_retries=3)
            )
        return {**sent, "rfc822_message_id": message_id}

    async def send(self, *, to: str, subject: str, text: str, html: str | None = None) -> dict:
        return await asyncio.to_thread(self._send, to=to, subject=subject, text=text, html=html)


def make_gmail(settings: Settings, allowed: frozenset[str]) -> GmailChannel:
    from googleapiclient.discovery import build

    if not settings.gmail_credentials_path or not settings.gmail_sender:
        raise ConfigError("Gmail is not configured: set GMAIL_CREDENTIALS_PATH and GMAIL_SENDER.")
    creds = load_credentials(Path(settings.gmail_credentials_path))
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return GmailChannel(service, settings.gmail_sender, allowed)


def main(argv: list[str]) -> int:
    if argv != ["authorize"]:
        print("usage: python -m app.backend.services.gmail authorize")
        return 2
    path = get_settings().gmail_credentials_path
    if not path:
        print("Set GMAIL_CREDENTIALS_PATH in .env first.", file=sys.stderr)
        return 1
    authorize(Path(path))
    print("Authorized. The token was written next to the client file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
