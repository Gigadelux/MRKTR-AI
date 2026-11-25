import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "SCHEMA.sql").read_text()
TABLES = re.findall(r"create table if not exists (\w+)", SQL)


def test_every_table_has_row_level_security():
    secured = set(re.findall(r"alter table (\w+)\s+enable row level security", SQL))
    assert set(TABLES) == secured


def test_expected_tables_exist():
    expected = {
        "users", "crm", "messages", "masked_messages", "tool_calls", "events", "kb_chunks",
        "email_drafts", "eval_datasets", "eval_dataset_records", "eval_experiments", "eval_results",
    }  # fmt: skip
    assert expected == set(TABLES)


def test_user_linked_tables_cascade_on_delete():
    for table in ("crm", "messages", "tool_calls", "events", "email_drafts"):
        block = SQL[SQL.index(f"create table if not exists {table} ") :].split(");", 1)[0]
        assert "references users (user_id) on delete cascade" in block, table


def test_schema_is_idempotent_by_construction():
    statements = re.findall(
        r"^create (?!or replace|extension|unique|index)(\w+)", SQL, re.MULTILINE
    )
    assert set(statements) == {"table"}
    assert all(f"create table if not exists {t} " in SQL for t in TABLES)
    assert not re.search(r"^create index (?!if not exists)", SQL, re.MULTILINE)


def test_crm_has_company_description_for_new_and_existing_databases():
    block = SQL[SQL.index("create table if not exists crm ") :].split(");", 1)[0]
    assert "company_description" in block  # fresh installs
    assert (
        "alter table crm add column if not exists company_description" in SQL
    )  # databases made earlier
    assert "comment on column crm.company_description" in SQL


def test_messages_have_metadata_for_new_and_existing_databases():
    block = SQL[SQL.index("create table if not exists messages ") :].split(");", 1)[0]
    assert "metadata" in block  # fresh installs
    assert "alter table messages add column if not exists metadata" in SQL  # earlier databases
    assert "comment on column messages.metadata" in SQL


def test_messages_store_type_and_transcript_but_never_audio():
    block = SQL[SQL.index("create table if not exists messages ") :].split(");", 1)[0]
    assert "audio_ref" not in block and "transcript_source" not in block  # fresh installs
    assert "check (message_type in ('text', 'voice', 'sticker', 'video'))" in block
    assert "check (message_type = 'sticker' or text is not null)" in block
    # databases made earlier: backfill, then drop the old columns
    assert "alter table messages add column if not exists message_type" in SQL
    assert "alter table messages drop column transcript_source" in SQL
    assert "alter table messages drop column if exists audio_ref" in SQL
    assert "comment on column messages.message_type" in SQL


def test_message_and_telegram_ids_are_unique_per_user_not_per_channel():
    assert "messages_channel_msg_uq" not in SQL.replace(
        "drop index if exists messages_channel_msg_uq", ""
    )
    assert "on messages (user_id, channel, channel_message_id)" in SQL
    assert "users_telegram_id_uq" in SQL and "channel_ids ->> 'telegram'" in SQL
