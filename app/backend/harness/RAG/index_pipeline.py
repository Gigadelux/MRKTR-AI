"""Build the local knowledge-base index: Milvus Lite file + fastembed dense and BM25 sparse vectors.

Documents: ``RAG_DATA_DIR`` (default ``gitignore/data/<company>/kb``), ``.md`` and ``.txt`` only.
Chunks: LangChain's RecursiveCharacterTextSplitter. Each chunk keeps its source path and the
collection date from ``_manifest.json`` when there is one.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymilvus import DataType, MilvusClient

from app.backend.core.company import CompanyProfile
from app.backend.core.settings import Settings

log = logging.getLogger(__name__)

DOC_SUFFIXES = {".md", ".txt"}
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
DENSE_DIM = 384  # BAAI/bge-small-en-v1.5
BATCH = 256  # rows per Milvus insert


def collection_name(company: CompanyProfile) -> str:
    return "kb_" + re.sub(r"[^a-z0-9_]", "_", company.name.lower())


def open_client(settings: Settings) -> MilvusClient:
    settings.rag_db_path.parent.mkdir(parents=True, exist_ok=True)
    return MilvusClient(str(settings.rag_db_path))


@lru_cache(maxsize=2)
def load_models(dense_model: str, sparse_model: str, cache_dir: str) -> tuple[Any, Any]:
    from fastembed import SparseTextEmbedding, TextEmbedding

    return (
        TextEmbedding(dense_model, cache_dir=cache_dir),
        SparseTextEmbedding(sparse_model, cache_dir=cache_dir),
    )


def models(settings: Settings) -> tuple[Any, Any]:
    settings.rag_cache_dir.mkdir(parents=True, exist_ok=True)
    return load_models(
        settings.rag_dense_model, settings.rag_sparse_model, str(settings.rag_cache_dir)
    )


def to_sparse(embedding: Any) -> dict[int, float]:
    return {int(i): float(v) for i, v in zip(embedding.indices, embedding.values, strict=True)}


def list_documents(docs_dir: Path) -> list[Path]:
    return sorted(p for p in docs_dir.rglob("*") if p.is_file() and p.suffix in DOC_SUFFIXES)


def chunk_documents(docs_dir: Path, default_collected_at: str = "") -> list[dict[str, str]]:
    """Split every document into chunks: {source, collected_at, text}."""
    manifest = docs_dir / "_manifest.json"
    dates: dict[str, str] = {}
    if manifest.is_file():
        pages = json.loads(manifest.read_text(encoding="utf-8")).get("pages", [])
        dates = {p["path"]: p.get("collected_at", "") for p in pages if p.get("path")}
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = []
    for path in list_documents(docs_dir):
        source = path.relative_to(docs_dir).as_posix()
        collected_at = dates.get(source, default_collected_at)
        for text in splitter.split_text(path.read_text(encoding="utf-8", errors="replace")):
            if text.strip():
                chunks.append({"source": source, "collected_at": collected_at, "text": text})
    return chunks


def create_collection(client: MilvusClient, name: str) -> None:
    if client.has_collection(name):
        client.drop_collection(name)
    schema = client.create_schema(auto_id=True)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("source", DataType.VARCHAR, max_length=1024)
    schema.add_field("collected_at", DataType.VARCHAR, max_length=32)
    schema.add_field("text", DataType.VARCHAR, max_length=8192)
    schema.add_field("dense", DataType.FLOAT_VECTOR, dim=DENSE_DIM)
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
    index = client.prepare_index_params()
    index.add_index("dense", index_type="AUTOINDEX", metric_type="COSINE")
    index.add_index("sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="IP")
    client.create_collection(name, schema=schema, index_params=index)


def build_index(settings: Settings, company: CompanyProfile) -> tuple[int, int]:
    """(Re)build the company's collection from RAG_DATA_DIR. Returns (files, chunks)."""
    docs_dir = settings.rag_docs_dir
    files = len(list_documents(docs_dir))
    chunks = chunk_documents(docs_dir, str(getattr(company, "collected_at", "") or ""))
    dense, sparse = models(settings)
    name = collection_name(company)
    client = open_client(settings)
    indexed = skipped = 0
    try:
        create_collection(client, name)
        for start in range(0, len(chunks), BATCH):
            batch = chunks[start : start + BATCH]
            texts = [c["text"] for c in batch]
            rows = []
            for c, d, s in zip(
                batch, dense.embed(texts, batch_size=32), sparse.embed(texts), strict=True
            ):
                weights = to_sparse(s)
                if not weights:  # no BM25 terms (only symbols/stopwords): Milvus rejects it
                    skipped += 1
                    continue
                rows.append({**c, "dense": d.tolist(), "sparse": weights})
            if rows:
                client.insert(name, rows)
            indexed += len(rows)
            log.info("indexed %s/%s chunks", start + len(batch), len(chunks))
    finally:
        client.close()
    if skipped:
        log.info("skipped %s chunks with no searchable terms", skipped)
    return files, indexed
