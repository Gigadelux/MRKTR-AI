from app.backend.harness.parsers.tags import parse_reply

NAMES = frozenset({"smile", "thinking"})


def test_valid_tag_is_stripped_and_returned():
    assert parse_reply("<e:smile> Hi there!", NAMES) == ("Hi there!", "smile")


def test_unknown_tag_gives_no_sticker_but_is_stripped():
    assert parse_reply("Hello <e:dance> friend", NAMES) == ("Hello friend", None)


def test_only_first_valid_tag_wins_and_all_are_stripped():
    text, sticker = parse_reply("<e:nope> A <e:thinking> B <e:smile> C", NAMES)
    assert sticker == "thinking"
    assert "<e:" not in text
    assert text == "A B C"


def test_malformed_tag_is_stripped():
    text, sticker = parse_reply("Hi <e:bad name!> there", NAMES)
    assert (text, sticker) == ("Hi there", None)


def test_no_tags():
    assert parse_reply("Plain text.\nSecond line.", NAMES) == ("Plain text.\nSecond line.", None)
