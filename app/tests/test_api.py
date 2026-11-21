from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.backend.app import create_app
from app.backend.core.errors import ConfigError
from app.backend.core.settings import Settings, get_settings


@pytest.fixture
def client(tmp_path):
    class TmpSettings(Settings):
        @property
        def data_root(self) -> Path:
            return tmp_path / "data"

        @property
        def temp_root(self) -> Path:
            return tmp_path / "temp"

    settings = TmpSettings(active_company="Acme")
    (settings.company_dir).mkdir(parents=True)
    (settings.company_dir / "company.yaml").write_text(
        yaml.safe_dump({"name": "Acme", "disclaimer": "Demo only."})
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


def test_health_and_company(client):
    assert client.get("/api/v1/health").json() == {
        "status": "ok",
        "company": "Acme",
        "source": "empty",
    }
    assert client.get("/api/v1/company").json()["disclaimer"] == "Demo only."


def test_empty_state_before_seeding(client):
    body = client.get("/api/v1/leads").json()
    assert body == {"source": "empty", "data": []}
    assert client.get("/api/v1/mock/status").json()["mock"] is False


def test_seed_then_delete_mock_data(client):
    assert client.post("/api/v1/mock/seed").json()["rows"]["users"] == 24
    for path in ("funnel", "leads", "masked", "approvals", "evals"):
        body = client.get(f"/api/v1/{path}").json()
        assert body["source"] == "mock", path  # every response says it is mock
    assert client.get("/api/v1/leads", params={"status": "booked"}).json()["data"]
    exp_id = client.get("/api/v1/evals").json()["data"][0]["experiment"]["id"]
    assert client.get(f"/api/v1/evals/{exp_id}").json()["data"]["results"]
    assert client.get("/api/v1/evals/nope").status_code == 404
    assert client.delete("/api/v1/mock").json()["removed"] is True
    assert client.get("/api/v1/leads").json()["source"] == "empty"


def test_logs_endpoint_handles_missing_file(client):
    assert client.get("/api/v1/logs").json() == {"lines": []}


def test_missing_company_profile_fails_with_a_clear_message(tmp_path):
    class Bare(Settings):
        @property
        def data_root(self) -> Path:
            return tmp_path

    with pytest.raises(ConfigError, match="No company profile"):
        with TestClient(create_app(Bare(active_company="Nobody"))):
            pass


def test_unset_company_fails_with_a_clear_message():
    with pytest.raises(ConfigError, match="ACTIVE_COMPANY is not set"):
        with TestClient(create_app(Settings(active_company=""))):
            pass
