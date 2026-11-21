"""Reads dashboard data from the mock JSON files. Each metric is one small function.

When the folder holds no mock files every method returns an empty result, so the UI shows
its empty state instead of failing.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.backend.data import mock
from app.backend.data.models import tables as t
from app.backend.data.models.views import (
    DraftView,
    ExperimentDetail,
    ExperimentSummary,
    FunnelStep,
    FunnelSummary,
    Lead,
    MaskedView,
    Source,
)

M = TypeVar("M", bound=BaseModel)


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


class MockRepository:
    def __init__(self, directory: Path) -> None:
        self.dir = directory

    def _load(self, name: str, model: type[M]) -> list[M]:
        path = self.dir / f"{name}.json"
        if not path.is_file():
            return []
        return [model.model_validate(row) for row in json.loads(path.read_text(encoding="utf-8"))]

    def source(self) -> Source:
        return "mock" if mock.is_mock(self.dir) else "empty"

    # --- funnel ---------------------------------------------------------
    def funnel(self) -> FunnelSummary:
        users = self._load("users", t.User)
        events = self._load("events", t.Event)
        messages = self._load("messages", t.Message)
        drafts = self._load("email_drafts", t.EmailDraft)

        by_type = Counter(e.type for e in events)
        started = by_type["token_redeemed"]
        # users who sent at least one Telegram message
        repliers = {m.user_id for m in messages if m.direction == "in" and m.channel == "telegram"}
        user_turns = sum(1 for m in messages if m.direction == "in" and m.channel == "telegram")
        decided = [d for d in drafts if d.status in ("approved", "sent")]
        unchanged = [d for d in decided if d.final_text == d.draft_text]
        steps = [
            FunnelStep(step="Emails sent", count=by_type["email_sent"]),
            FunnelStep(step="Opened Telegram", count=started),
            FunnelStep(step="Chose a mode", count=by_type["mode_chosen"]),
            FunnelStep(step="Replied", count=len(repliers)),
            FunnelStep(step="Qualified", count=by_type["qualified"]),
            FunnelStep(step="Booked", count=by_type["booked"]),
        ]
        return FunnelSummary(
            steps=steps,
            click_through=_ratio(started, by_type["email_sent"]),
            reply_rate=_ratio(len(repliers), started),
            avg_turns=round(user_turns / len(repliers), 1) if repliers else None,
            mode_split=dict(Counter(u.pref_mode for u in users if u.pref_mode)),
            drafts_approved_unchanged=_ratio(len(unchanged), len(decided)),
        )

    # --- leads and conversations ---------------------------------------
    def leads(self, status: str | None = None) -> list[Lead]:
        users = self._load("users", t.User)
        crm = {c.user_id: c for c in self._load("crm", t.Crm)}
        counts = Counter(m.user_id for m in self._load("messages", t.Message))
        out = [Lead(user=u, crm=crm.get(u.user_id), messages=counts[u.user_id]) for u in users]
        if status:
            out = [lead for lead in out if lead.crm and lead.crm.status == status]
        return out

    def conversation(self, user_id: str) -> list[t.Message]:
        rows = [m for m in self._load("messages", t.Message) if m.user_id == user_id]
        return sorted(rows, key=lambda m: m.created_at)

    # --- safety ---------------------------------------------------------
    def masked(self) -> list[MaskedView]:
        messages = {m.id: m for m in self._load("messages", t.Message)}
        emails = {u.user_id: u.email for u in self._load("users", t.User)}
        out = []
        for row in self._load("masked_messages", t.MaskedMessage):
            msg = messages.get(row.message_id)
            out.append(
                MaskedView(masked=row, message=msg, email=emails.get(msg.user_id) if msg else None)
            )
        return out

    def decoys(self) -> list[dict]:
        """Benign decoy cases from the security evals. Nothing in them looks malicious, so guards pass them."""
        exps = {e.id: e for e in self._load("eval_experiments", t.EvalExperiment)}
        rows = []
        for r in self._load("eval_results", t.EvalResult):
            if "benign_decoy" in r.tags and r.span_type == "eval":
                exp = exps.get(r.experiment_id)
                rows.append({
                    "experiment": exp.name if exp else r.experiment_id,
                    "version": exp.version if exp else None,
                    "input": r.input,
                    "masked": r.metadata.get("masked", False),
                    "decoy_resisted": r.scores.get("decoy_resisted"),
                })  # fmt: skip
        return rows

    # --- approvals ------------------------------------------------------
    def drafts(self, status: str | None = None) -> list[DraftView]:
        emails = {u.user_id: u.email for u in self._load("users", t.User)}
        messages = {m.id: m for m in self._load("messages", t.Message)}
        out = []
        for d in self._load("email_drafts", t.EmailDraft):
            if status and d.status != status:
                continue
            incoming = messages.get(d.in_reply_to) if d.in_reply_to else None
            out.append(
                DraftView(
                    draft=d,
                    email=emails.get(d.user_id),
                    incoming=incoming.text if incoming else None,
                )
            )
        return sorted(out, key=lambda v: v.draft.created_at, reverse=True)

    # --- evals ----------------------------------------------------------
    def _summaries(self) -> tuple[list[ExperimentSummary], dict[str, list[t.EvalResult]]]:
        results: dict[str, list[t.EvalResult]] = defaultdict(list)
        for r in self._load("eval_results", t.EvalResult):
            results[r.experiment_id].append(r)
        out = []
        for exp in self._load("eval_experiments", t.EvalExperiment):
            roots = [r for r in results[exp.id] if r.span_type == "eval"]
            out.append(ExperimentSummary(
                experiment=exp, cases=len(roots),
                scores=_mean_by_key([r.scores for r in roots]),
                metrics=_mean_by_key([r.metrics for r in roots]),
            ))  # fmt: skip
        return sorted(out, key=lambda s: s.experiment.created_at), results

    def experiments(self) -> list[ExperimentSummary]:
        return self._summaries()[0]

    def experiment(self, experiment_id: str) -> ExperimentDetail | None:
        summaries, results = self._summaries()
        for s in summaries:
            if s.experiment.id == experiment_id:
                ordered = sorted(results[experiment_id], key=lambda r: r.created_at)
                return ExperimentDetail(summary=s, results=ordered)
        return None


def _mean_by_key(dicts: list[dict]) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for d in dicts:
        for k, v in d.items():
            if v is not None:
                values[k].append(v)
    return {k: round(sum(v) / len(v), 3) for k, v in values.items()}
