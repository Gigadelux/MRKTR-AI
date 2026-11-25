import base64
import email
from email import policy

import pytest

from app.backend.core.allowlists import RecipientNotAllowed
from app.backend.services.gmail import GmailChannel

ALLOWED = frozenset({"friend@example.com"})


def decode(raw: str) -> email.message.EmailMessage:
    return email.message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)


def test_build_raw_plain_and_html():
    ch = GmailChannel(service=None, sender="me@example.com", allowed=ALLOWED)
    msg = decode(ch.build_raw(to="friend@example.com", subject="Hi", text="plain", html="<p>x</p>"))
    assert msg["To"] == "friend@example.com"
    assert msg["Cc"] is None and msg["Bcc"] is None
    assert msg.get_body(("plain",)).get_content().strip() == "plain"
    assert msg.get_body(("html",)).get_content().strip() == "<p>x</p>"


def test_build_raw_blocks_non_allowlisted():
    ch = GmailChannel(service=None, sender="me@example.com", allowed=ALLOWED)
    with pytest.raises(RecipientNotAllowed):
        ch.build_raw(to="stranger@example.com", subject="Hi", text="x")


def test_subject_header_injection_is_rejected():
    ch = GmailChannel(service=None, sender="me@example.com", allowed=ALLOWED)
    with pytest.raises(ValueError):
        ch.build_raw(to="friend@example.com", subject="Hi\nBcc: x@example.com", text="x")
