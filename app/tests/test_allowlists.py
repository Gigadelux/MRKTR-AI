import pytest
import yaml

from app.backend.core.allowlists import (
    RecipientNotAllowed,
    check_recipient,
    is_telegram_allowed,
    load_email_allowlist,
)
from app.tests.conftest import make_user

ALLOWED = frozenset({"friend@example.com"})


def test_allowlisted_bare_address_passes():
    assert check_recipient("Friend@Example.com", ALLOWED) == "friend@example.com"


@pytest.mark.parametrize(
    "value",
    [
        "stranger@example.com",
        "Friend <friend@example.com>",
        "friend@example.com, other@example.com",
        "friend@example.com\nBcc: other@example.com",
        "friend@example.com;other@example.com",
        "not-an-address",
        "",
    ],
)
def test_everything_else_is_rejected(value):
    with pytest.raises(RecipientNotAllowed):
        check_recipient(value, ALLOWED)


def test_allowlist_file(settings):
    assert load_email_allowlist(settings) == frozenset()  # no file: nothing can be sent
    (settings.company_dir / "allowlist.yaml").write_text(
        yaml.safe_dump({"emails": ["Friend@Example.com", ""]})
    )
    assert load_email_allowlist(settings) == ALLOWED


def test_telegram_needs_redeemed_token_and_consent():
    assert is_telegram_allowed(make_user())
    assert not is_telegram_allowed(make_user(consent_at=None))
    assert not is_telegram_allowed(make_user(channel_ids={}))
