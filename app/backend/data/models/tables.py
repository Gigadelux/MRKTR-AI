"""Pydantic models that mirror the tables in SCHEMA.sql."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PrefMode = Literal["audio_transcript", "audio_only", "text_only"]
CrmStatus = Literal["new", "contacted", "engaged", "qualified", "booked", "not_now", "unsubscribed"]
Channel = Literal["email", "telegram"]
TranscriptSource = Literal["user_text", "stt", "agent_text", "tts_script"]
DraftClass = Literal["interested", "question", "not_now", "unsubscribe"]
DraftStatus = Literal["pending", "approved", "rejected", "sent"]
SpanType = Literal["eval", "task", "llm", "function", "tool", "score", "classifier"]


class User(BaseModel):
    user_id: str
    channel_ids: dict[str, Any] = Field(default_factory=dict)
    email: str | None = None
    start_token: str | None = None
    pref_mode: PrefMode | None = None
    consent_at: datetime | None = None
    company: str
    created_at: datetime


class Crm(BaseModel):
    user_id: str
    company_name: str | None = None
    company_description: str | None = None
    role: str | None = None
    industry: str | None = None
    size: str | None = None
    use_case: str | None = None
    budget: str | None = None
    timeline: str | None = None
    status: CrmStatus = "new"
    updated_at: datetime


class Message(BaseModel):
    id: str
    user_id: str
    channel: Channel
    channel_message_id: str | None = None
    direction: Literal["in", "out"]
    text: str | None = None
    audio_ref: str | None = None
    transcript_source: TranscriptSource
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MaskedMessage(BaseModel):
    id: str
    message_id: str
    original_text: str
    masked_text: str
    detector: str
    score: float | None = None
    reason: str | None = None
    created_at: datetime


class ToolCall(BaseModel):
    id: str
    user_id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    refused_reason: str | None = None
    created_at: datetime


class Event(BaseModel):
    id: str
    user_id: str | None = None
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EmailDraft(BaseModel):
    id: str
    user_id: str
    in_reply_to: str | None = None
    classification: DraftClass
    draft_text: str
    final_text: str | None = None
    status: DraftStatus = "pending"
    decided_at: datetime | None = None
    created_at: datetime


class EvalExperiment(BaseModel):
    id: str
    name: str
    version: str | None = None
    suite: Literal["performance", "security"]
    description: str | None = None
    dataset_id: str | None = None
    braintrust_experiment_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class EvalResult(BaseModel):
    """One span of an eval trace, with Braintrust-style field names."""

    id: str
    experiment_id: str
    dataset_record_id: str | None = None
    span_id: str
    root_span_id: str
    span_parents: list[str] = Field(default_factory=list)
    span_type: SpanType | None = None
    span_name: str | None = None
    input: Any = None
    output: Any = None
    expected: Any = None
    error: str | None = None
    scores: dict[str, float | None] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    created_at: datetime
