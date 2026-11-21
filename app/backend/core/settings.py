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
