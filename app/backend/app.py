"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.backend.core.company import load_company
from app.backend.core.settings import Settings, get_settings
from app.backend.endpoints.v1.api import router

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.company = load_company(
            settings
        )  # fails with a clear message if the profile is missing
        log.info("API started for company %s", app.state.company.name)
        yield
        log.info("API stopped")

    app = FastAPI(title="mrktr AI", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    return app
