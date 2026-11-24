import json

from app.backend.data import mock
from app.backend.data.models import tables as t
from app.backend.data.repositories.mock_repository import MockRepository


def test_build_is_deterministic():
    a, b = mock.build(), mock.build()
    assert {k: len(v) for k, v in a.items()} == {k: len(v) for k, v in b.items()}
    assert [u.email for u in a["users"]] == [u.email for u in b["users"]]


def test_mock_people_are_fictional():
    users = mock.build()["users"]
    assert users and all(u.email.endswith("@example.com") for u in users)


def test_text_only_users_never_get_a_voice_note():
    tables = mock.build()
    text_only = {u.user_id for u in tables["users"] if u.pref_mode == "text_only"}
    sent = [
        c
        for c in tables["tool_calls"]
        if c.tool == "send_voice_note" and c.user_id in text_only and c.refused_reason is None
    ]
    voice = [m for m in tables["messages"] if m.user_id in text_only and m.audio_ref]
    assert not sent
    assert all(m.direction == "in" for m in voice)  # users may send voice; the agent may not


def test_masked_originals_are_not_in_messages():
    tables = mock.build()
    texts = " ".join(m.text or "" for m in tables["messages"])
    for row in tables["masked_messages"]:
        assert mock.MASK in row.masked_text
        assert row.original_text not in texts


def test_eval_scores_stay_between_zero_and_one():
    for r in mock.build()["eval_results"]:
        assert all(v is None or 0 <= v <= 1 for v in r.scores.values())
        assert not r.span_parents or r.root_span_id in r.span_parents


def test_seed_and_delete_only_touch_mock_files(tmp_path):
    directory = tmp_path / "mock"
    counts = mock.seed_mock(directory)
    assert counts["users"] == 24 and mock.is_mock(directory)
    assert all((directory / f"{n}.json").is_file() for n in mock.TABLE_FILES)
    (directory / "keep.txt").write_text("not mock")
    assert mock.delete_mock(directory) is True
    assert (directory / "keep.txt").exists() and not mock.is_mock(directory)
    assert mock.delete_mock(tmp_path / "missing") is False


def test_written_files_validate_against_the_models(tmp_path):
    mock.seed_mock(tmp_path)
    rows = json.loads((tmp_path / "users.json").read_text())
    assert t.User.model_validate(rows[0]).company == "MOCK"


def test_repository_is_empty_without_mock_data(tmp_path):
    repo = MockRepository(tmp_path)
    assert repo.source() == "empty"
    funnel = repo.funnel()
    assert funnel.click_through is None and funnel.avg_turns is None
    assert repo.leads() == [] and repo.experiments() == []


def test_funnel_counts_match_events(tmp_path):
    mock.seed_mock(tmp_path)
    repo = MockRepository(tmp_path)
    assert repo.source() == "mock"
    steps = {s.step: s.count for s in repo.funnel().steps}
    assert steps["Emails sent"] == 24
    assert steps["Booked"] <= steps["Qualified"] <= steps["Replied"] <= steps["Opened Telegram"]
    detail = repo.experiment(repo.experiments()[0].experiment.id)
    assert detail and [r.created_at for r in detail.results] == sorted(
        r.created_at for r in detail.results
    )


def test_qualified_leads_have_a_company_description():
    tables = mock.build()
    qualified = [c for c in tables["crm"] if c.status in ("qualified", "booked")]
    assert qualified and all(c.company_name and c.company_description for c in qualified)
    assert all(
        c.company_description is None
        for c in tables["crm"]
        if c.status not in ("qualified", "booked")
    )
    calls = [c for c in tables["tool_calls"] if c.tool == "update_crm"]
    assert calls and all(c.args["company_description"] for c in calls)


def test_message_metadata_holds_threading_and_usage_when_present():
    messages = mock.build()["messages"]
    emails = [m for m in messages if m.channel == "email"]
    assert emails and all(m.metadata["gmail_thread_id"].startswith("mock-") for m in emails)
    tts = [m for m in messages if m.transcript_source == "tts_script"]
    assert tts and all(m.metadata["usage"]["tts_characters"] == len(m.text) for m in tts)
