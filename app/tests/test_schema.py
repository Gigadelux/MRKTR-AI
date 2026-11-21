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
