"""Load the active company profile (``gitignore/data/<company>/company.yaml``)."""

from __future__ import annotations

import yaml
from pydantic import BaseModel, ConfigDict

from app.backend.core.errors import ConfigError
from app.backend.core.settings import Settings


class Persona(BaseModel):
    name: str = "Assistant"
    tone: str = ""
    languages: list[str] = []


class CompanyProfile(BaseModel):
    """The public part of a company profile. Extra keys (kb_sources, icp...) are kept but unused here."""

    model_config = ConfigDict(extra="allow")

    name: str
    website: str = ""
    description: str = ""
    disclaimer: str = ""
    persona: Persona = Persona()


def load_company(settings: Settings) -> CompanyProfile:
    if not settings.active_company:
        raise ConfigError(
            "ACTIVE_COMPANY is not set. Put the name of a folder under gitignore/data/ in .env."
        )
    path = settings.company_dir / "company.yaml"
    if not path.is_file():
        raise ConfigError(
            f"No company profile at {path}. Create gitignore/data/{settings.active_company}/company.yaml "
            "or set ACTIVE_COMPANY to an existing folder."
        )
    return CompanyProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
