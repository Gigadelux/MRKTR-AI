"""Shapes returned by the API (derived from the tables, not stored)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.backend.data.models.tables import (
    Crm,
    EmailDraft,
    EvalExperiment,
    EvalResult,
    MaskedMessage,
    Message,
    User,
)

Source = Literal["mock", "empty"]


class FunnelStep(BaseModel):
    step: str
    count: int


class FunnelSummary(BaseModel):
    """Funnel counts and rates. A rate is None when its denominator is zero."""

    steps: list[FunnelStep]
    click_through: float | None  # token redemptions / emails sent
    reply_rate: float | None  # users who replied / users who started
    avg_turns: float | None  # user messages per replying user
    mode_split: dict[str, int]
    drafts_approved_unchanged: float | None  # decided drafts approved without edits


class Lead(BaseModel):
    user: User
    crm: Crm | None
    messages: int


class MaskedView(BaseModel):
    masked: MaskedMessage
    message: Message | None
    email: str | None


class ExperimentSummary(BaseModel):
    experiment: EvalExperiment
    cases: int
    scores: dict[str, float]  # mean of each score across the root spans
    metrics: dict[str, float]  # mean of each metric across the root spans


class ExperimentDetail(BaseModel):
    summary: ExperimentSummary
    results: list[EvalResult]


class DraftView(BaseModel):
    draft: EmailDraft
    email: str | None
    incoming: str | None


class Envelope(BaseModel):
    """Every response says whether its data is mock or empty (live data arrives with Supabase)."""

    source: Source
    data: Any
