"""Application settings, read from environment variables and ``.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime settings. Company-specific values live in the company profile, not here."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    active_company: str = ""  # folder name under gitignore/data/, set in .env
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    streamlit_port: int = 8501

    # LLM (OpenAI-compatible: OpenRouter, Venice AI)
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # Channels
    telegram_bot_token: str = ""
    gmail_credentials_path: str = ""  # OAuth client file; the token is written next to it
    gmail_sender: str = ""  # From: address of the outreach emails

    # Voice (ElevenLabs)
    tts_api_key: str = ""
    tts_voice_id: str = ""
    max_voice_notes_per_conversation: int = 5
    # No content guard exists yet: voice notes are refused unless this is set (dev only).
    dev_allow_unguarded_voice: bool = False

    # Database (Supabase, service-role key, dev project)
    supabase_url: str = ""
    supabase_key: str = ""

    # RAG (Milvus Lite + fastembed, all local)
    rag_data_dir: str = ""  # empty = gitignore/data/<ACTIVE_COMPANY>/kb
    rag_dense_model: str = "BAAI/bge-small-en-v1.5"
    rag_sparse_model: str = "Qdrant/bm25"

    @property
    def api_base_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def data_root(self) -> Path:
        return ROOT / "gitignore" / "data"

    @property
    def company_dir(self) -> Path:
        return self.data_root / self.active_company

    @property
    def rag_docs_dir(self) -> Path:
        if not self.rag_data_dir:
            return self.company_dir / "kb"
        path = Path(self.rag_data_dir)
        return path if path.is_absolute() else ROOT / path

    @property
    def rag_db_path(self) -> Path:
        return self.temp_root / "rag" / "milvus.db"

    @property
    def rag_cache_dir(self) -> Path:
        return self.temp_root / "cache" / "fastembed"

    @property
    def outbox_dir(self) -> Path:
        return self.temp_root / "outbox"

    @property
    def temp_root(self) -> Path:
        return ROOT / "gitignore" / "temp"

    @property
    def mock_dir(self) -> Path:
        return self.temp_root / "mock"

    @property
    def log_file(self) -> Path:
        return self.temp_root / "logs" / "api.log"


@lru_cache
def get_settings() -> Settings:
    return Settings()
