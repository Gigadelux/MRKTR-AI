import json

import pytest

from app.backend.core.errors import ConfigError
from app.backend.core.settings import ROOT
from app.backend.core.start import ensure_rag
from app.backend.harness.RAG import index_pipeline


def write_kb(settings, files: dict[str, str]):
    kb = settings.rag_docs_dir
    kb.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (kb / name).parent.mkdir(parents=True, exist_ok=True)
        (kb / name).write_text(text)
    return kb


def test_chunks_keep_source_and_manifest_date(settings):
    kb = write_kb(settings, {"a.md": "word " * 600, "sub/b.txt": "short", "skip.json": "{}"})
    (kb / "_manifest.json").write_text(
        json.dumps({"pages": [{"path": "a.md", "collected_at": "2026-11-20"}]})
    )
    chunks = index_pipeline.chunk_documents(kb, default_collected_at="2026-01-01")
    sources = {c["source"] for c in chunks}
    assert sources == {"a.md", "sub/b.txt"}  # .json is not a document
    assert sum(c["source"] == "a.md" for c in chunks) > 1  # split by the splitter
    assert all(len(c["text"]) <= index_pipeline.CHUNK_SIZE for c in chunks)
    assert {c["collected_at"] for c in chunks if c["source"] == "a.md"} == {"2026-11-20"}
    assert {c["collected_at"] for c in chunks if c["source"] == "sub/b.txt"} == {"2026-01-01"}


def test_missing_or_empty_data_dir_raises(settings, company):
    with pytest.raises(ConfigError, match="No RAG documents"):
        ensure_rag(settings, company)
    write_kb(settings, {"notes.json": "{}"})
    with pytest.raises(ConfigError, match="No RAG documents"):
        ensure_rag(settings, company)


def test_data_dir_outside_gitignore_data_raises(settings, company, tmp_path):
    settings.rag_data_dir = str(tmp_path / "elsewhere")
    with pytest.raises(ConfigError, match="inside"):
        ensure_rag(settings, company)


def test_builds_when_not_initialized_then_skips(settings, company, monkeypatch):
    write_kb(settings, {"a.md": "hello"})
    built = []

    def fake_build(s, c):
        built.append(c.name)
        return 1, 3

    monkeypatch.setattr(index_pipeline, "build_index", fake_build)
    ensure_rag(settings, company)  # no db file yet
    assert built == ["Acme"]

    class Client:
        def has_collection(self, name):
            return True

        def get_collection_stats(self, name):
            return {"row_count": 3}

        def close(self):
            pass

    settings.rag_db_path.parent.mkdir(parents=True)
    settings.rag_db_path.write_bytes(b"")
    monkeypatch.setattr(index_pipeline, "open_client", lambda s: Client())
    ensure_rag(settings, company)  # initialized: no rebuild
    assert built == ["Acme"]


def test_real_index_and_hybrid_search(settings, company, monkeypatch):
    """Real Milvus Lite + fastembed. Skipped when the models can't be loaded (offline)."""
    shared_cache = ROOT / "gitignore" / "temp" / "cache" / "fastembed"  # reuse downloaded models
    monkeypatch.setattr(type(settings), "rag_cache_dir", property(lambda s: shared_cache))
    try:
        index_pipeline.models(settings)
    except Exception as exc:  # pragma: no cover - depends on the network
        pytest.skip(f"fastembed models unavailable: {exc}")
    from app.backend.harness.RAG.mcp_rag import search

    write_kb(
        settings,
        {
            "pricing.md": "The Starter plan costs 5 dollars per month and includes voice cloning.",
            "rockets.md": "Rockets need fuel, engines and a launch pad.",
        },
    )
    ensure_rag(settings, company)

    def must_not_rebuild(s, c):
        raise AssertionError("an initialized index was rebuilt")

    monkeypatch.setattr(index_pipeline, "build_index", must_not_rebuild)
    ensure_rag(settings, company)  # real db: second start only checks

    hits = search("how much is the starter plan", k=2, settings=settings, company=company)
    assert hits[0].source == "pricing.md"
