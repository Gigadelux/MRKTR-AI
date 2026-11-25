"""Startup service: make sure the RAG index exists before anything else starts."""

from __future__ import annotations

import logging

from app.backend.core.company import CompanyProfile
from app.backend.core.errors import ConfigError
from app.backend.core.settings import Settings

log = logging.getLogger(__name__)


def ensure_rag(settings: Settings, company: CompanyProfile) -> None:
    """Check the RAG structure; build it if it is not initialized.

    1. RAG_DATA_DIR must be inside gitignore/data/ and contain .md/.txt documents,
       otherwise raise ConfigError.
    2. Initialized = the Milvus db file exists and the company collection has rows: return.
    3. Otherwise run the index pipeline.
    """
    from app.backend.harness.RAG import index_pipeline as rag  # heavy imports, only at startup

    docs_dir = settings.rag_docs_dir.resolve()
    if not docs_dir.is_relative_to(settings.data_root.resolve()):
        raise ConfigError(f"RAG_DATA_DIR must be inside {settings.data_root}, got {docs_dir}.")
    if not docs_dir.is_dir() or not rag.list_documents(docs_dir):
        raise ConfigError(
            f"No RAG documents in {docs_dir}: add .md/.txt files or set RAG_DATA_DIR in .env."
        )

    name = rag.collection_name(company)
    if settings.rag_db_path.exists():  # milvus-lite 3 stores the db as a directory
        client = rag.open_client(settings)
        try:
            rows = (
                int(client.get_collection_stats(name).get("row_count", 0))
                if client.has_collection(name)
                else 0
            )
        finally:
            client.close()
        if rows > 0:
            log.info("RAG ready: collection %s has %s chunks", name, rows)
            return

    log.info(
        "RAG not initialized: indexing %s (first run downloads the embedding models)", docs_dir
    )
    files, chunks = rag.build_index(settings, company)
    if chunks == 0:
        raise ConfigError(f"RAG indexing produced no chunks from {docs_dir}.")
    log.info("RAG ready: indexed %s files into %s chunks (%s)", files, chunks, name)
