from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from app.backend.core.company import CompanyProfile
from app.backend.core.settings import Settings
from app.backend.data.models.tables import Crm, User

NOW = datetime(2026, 11, 25, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path):
    class TmpSettings(Settings):
        @property
        def data_root(self) -> Path:
            return tmp_path / "data"

        @property
        def temp_root(self) -> Path:
            return tmp_path / "temp"

    s = TmpSettings(_env_file=None, active_company="Acme")
    s.company_dir.mkdir(parents=True)
    (s.company_dir / "company.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "Acme",
                "website": "https://acme.example",
                "description": "Acme makes fictional rockets.",
                "disclaimer": "Fictional demo company.",
                "persona": {"name": "Robo", "tone": "Warm", "languages": ["en"]},
                "products": [{"name": "Rocket", "summary": "A fictional rocket."}],
                "qualification_questions": ["What are you launching?"],
            }
        )
    )
    return s


@pytest.fixture
def company(settings) -> CompanyProfile:
    from app.backend.core.company import load_company

    return load_company(settings)


def make_user(**kw) -> User:
    base = {
        "user_id": "u1",
        "channel_ids": {"telegram": 42},
        "email": "friend@example.com",
        "start_token": None,
        "pref_mode": "audio_transcript",
        "consent_at": NOW,
        "company": "Acme",
        "created_at": NOW,
    }
    return User.model_validate({**base, **kw})


def make_crm(**kw) -> Crm:
    base = {"user_id": "u1", "company_name": "Beta Corp", "role": "CTO", "updated_at": NOW}
    return Crm.model_validate({**base, **kw})
