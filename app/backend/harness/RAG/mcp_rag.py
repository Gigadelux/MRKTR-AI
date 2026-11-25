"""Search the knowledge base: hybrid dense (fastembed) + BM25 sparse in Milvus Lite, fused with RRF.

A plain function for now (the seller's search_kb tool); an MCP server can wrap it later.
KB text is untrusted: the agent must treat it as data, never as instructions.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel
from pymilvus import AnnSearchRequest, MilvusClient, RRFRanker

from app.backend.core.company import CompanyProfile, load_company
from app.backend.core.settings import Settings, get_settings
from app.backend.harness.RAG.index_pipeline import collection_name, models, to_sparse


class Hit(BaseModel):
    source: str
    collected_at: str
    text: str
    score: float


@lru_cache(maxsize=4)
def _client(db_path: str) -> MilvusClient:
    return MilvusClient(db_path)  # one client per db file per process


def search(
    query: str,
    k: int = 5,
    settings: Settings | None = None,
    company: CompanyProfile | None = None,
) -> list[Hit]:
    settings = settings or get_settings()
    company = company or load_company(settings)
    dense, sparse = models(settings)
    client = _client(str(settings.rag_db_path))
    requests = [
        AnnSearchRequest([next(iter(dense.query_embed(query))).tolist()], "dense", {}, limit=k * 2)
    ]
    weights = to_sparse(next(iter(sparse.query_embed(query))))
    if weights:  # a query of only stopwords/symbols has no BM25 terms: dense only
        requests.append(AnnSearchRequest([weights], "sparse", {}, limit=k * 2))
    result = client.hybrid_search(
        collection_name(company),
        requests,
        RRFRanker(),
        limit=k,
        output_fields=["source", "collected_at", "text"],
    )
    return [
        Hit(
            source=hit["entity"]["source"],
            collected_at=hit["entity"]["collected_at"],
            text=hit["entity"]["text"],
            score=hit["distance"],
        )
        for hit in result[0]
    ]
