import json
import urllib.error

from app.backend.services import kb_scraper as kb

INDEX = """# Overview

## Docs

- [Models](https://example.com/docs/overview/models.md): Learn about models
- [Nested](https://example.com/docs/overview/sub/llms.txt)
- [No description](https://example.com/docs/overview/plain.md)
not a link line
"""


def test_parse_index_extracts_title_url_description():
    assert kb.parse_index(INDEX) == [
        ("Models", "https://example.com/docs/overview/models.md", "Learn about models"),
        ("Nested", "https://example.com/docs/overview/sub/llms.txt", ""),
        ("No description", "https://example.com/docs/overview/plain.md", ""),
    ]


def test_url_to_relpath():
    assert kb.url_to_relpath("https://x.io/docs/overview/a/b.md", "overview") == "overview/a/b.md"
    assert kb.url_to_relpath("https://x.io/pricing/api", "site") == "site/pricing/api.md"
    assert kb.url_to_relpath("https://x.io/", "site") == "site/home.md"
    assert (
        kb.url_to_relpath("https://x.io/docs/openapi/a.json", "openapi", raw_file=True)
        == "openapi/a.json"
    )


def test_front_matter_round_trip():
    page = kb.Page(url="https://x.io/p", section="s", title="T", description='say "hi"')
    head = kb.build_front_matter(page, "2026-11-20")
    assert 'source_url: "https://x.io/p"' in head
    assert "collected_at: 2026-11-20" in head
    fields, rest = kb.split_front_matter('---\ntitle: "Page title"\nmeta:\n  a: b\n---\nBody\n')
    assert fields == {"title": "Page title"} and rest == "Body\n"
    assert kb.split_front_matter("No front matter") == ({}, "No front matter")


def test_collect_writes_pages_and_merges_manifest(tmp_path, monkeypatch):
    def fake_fetch(url, accept=None, retries=3, timeout=40):
        if url.endswith("/llms.txt"):
            return b"- [A](https://x.io/docs/s/a.md): about a\n", "text/plain"
        if url.endswith("/gone.md"):
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        return b"# A\n", "text/markdown"

    monkeypatch.setattr(kb, "fetch", fake_fetch)
    sources = [
        {"name": "s", "type": "llms_index", "index": "https://x.io/docs/s/llms.txt"},
        {"name": "t", "type": "pages", "urls": ["https://x.io/gone.md"]},
    ]
    results = kb.collect(sources, tmp_path, "2026-11-20", delay=0)
    assert {r.status for r in results} == {"ok", "unavailable"}
    text = (tmp_path / "s" / "a.md").read_text()
    assert text.startswith("---\n") and 'description: "about a"' in text and text.endswith("# A\n")

    # re-running one source keeps the other source's manifest entries
    kb.collect(sources, tmp_path, "2026-11-20", only="s", delay=0)
    manifest = json.loads((tmp_path / "_manifest.json").read_text())
    assert {p["section"] for p in manifest["pages"]} == {"s", "t"}
    assert next(p for p in manifest["pages"] if p["section"] == "s")["status"] == "skipped"
