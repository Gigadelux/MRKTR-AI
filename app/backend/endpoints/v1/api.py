"""HTTP API for the dashboard. All routes are read-only except the mock-data controls."""

from __future__ import annotations

import logging
from collections import deque
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.backend.core.company import CompanyProfile
from app.backend.core.settings import Settings, get_settings
from app.backend.data import mock
from app.backend.data.models.views import Envelope
from app.backend.data.repositories.base import Repository
from app.backend.data.repositories.mock_repository import MockRepository

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_repo(settings: SettingsDep) -> Repository:
    """Built per request, so seeding or deleting mock data shows up immediately."""
    return MockRepository(settings.mock_dir)


RepoDep = Annotated[Repository, Depends(get_repo)]


def _wrap(repo: Repository, data: object) -> Envelope:
    return Envelope(source=repo.source(), data=data)


@router.get("/health")
def health(request: Request, repo: RepoDep) -> dict:
    company: CompanyProfile = request.app.state.company
    return {"status": "ok", "company": company.name, "source": repo.source()}


@router.get("/company")
def company(request: Request) -> CompanyProfile:
    return request.app.state.company


@router.get("/funnel")
def funnel(repo: RepoDep) -> Envelope:
    return _wrap(repo, repo.funnel())


@router.get("/leads")
def leads(repo: RepoDep, status: str | None = None) -> Envelope:
    return _wrap(repo, repo.leads(status))


@router.get("/conversations/{user_id}")
def conversation(user_id: str, repo: RepoDep) -> Envelope:
    return _wrap(repo, repo.conversation(user_id))


@router.get("/masked")
def masked(repo: RepoDep) -> Envelope:
    return _wrap(repo, {"masked": repo.masked(), "decoys": repo.decoys()})


@router.get("/approvals")
def approvals(repo: RepoDep, status: str | None = None) -> Envelope:
    return _wrap(repo, repo.drafts(status))


@router.get("/evals")
def evals(repo: RepoDep) -> Envelope:
    return _wrap(repo, repo.experiments())


@router.get("/evals/{experiment_id}")
def eval_detail(experiment_id: str, repo: RepoDep) -> Envelope:
    detail = repo.experiment(experiment_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return _wrap(repo, detail)


@router.get("/logs")
def logs(settings: SettingsDep, lines: Annotated[int, Query(ge=1, le=1000)] = 200) -> dict:
    path = settings.log_file
    if not path.is_file():
        return {"lines": []}
    with path.open(encoding="utf-8", errors="replace") as fh:
        return {"lines": [line.rstrip("\n") for line in deque(fh, maxlen=lines)]}


@router.get("/mock/status")
def mock_status(settings: SettingsDep) -> dict:
    return {"mock": mock.is_mock(settings.mock_dir), "directory": "gitignore/temp/mock"}


@router.post("/mock/seed")
def mock_seed(settings: SettingsDep) -> dict:
    counts = mock.seed_mock(settings.mock_dir)
    log.info("mock data seeded: %s", counts)
    return {"mock": True, "rows": counts}


@router.delete("/mock")
def mock_delete(settings: SettingsDep) -> dict:
    removed = mock.delete_mock(settings.mock_dir)
    log.info("mock data deleted (removed=%s)", removed)
    return {"mock": False, "removed": removed}
