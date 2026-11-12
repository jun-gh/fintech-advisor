"""Pydantic v2 schemas for Compliance Copilot queries, structured citations, and audit views."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CopilotQueryRequest(BaseModel):
    """Incoming compliance question for the Card Dispute & Chargeback Copilot."""

    query: str = Field(min_length=3, max_length=2000)
    category: str | None = Field(
        default=None,
        max_length=64,
        description="Optional SOP category filter (e.g. regulation_e, card_network_chargebacks).",
    )
    top_k: int = Field(default=5, ge=1, le=10)


class Citation(BaseModel):
    """Pinpoint policy citation backed by a retrieved context chunk."""

    chunk_id: str
    source_id: str
    document_title: str
    document_version: str
    section_title: str
    excerpt: str


class CopilotLLMOutput(BaseModel):
    """Strict structured output contract enforced on Gemini generations."""

    is_supported: bool = Field(
        description=(
            "True ONLY if the provided <policy_context> chunks contain direct evidence "
            "answering the user's question. False if evidence is missing or out of scope."
        )
    )
    answer: str = Field(
        description=(
            "Clear, concise compliance answer strictly grounded in the policy chunks, "
            "referencing rule numbers/timelines/thresholds accurately. If unsupported, explain "
            "what policy information is missing."
        )
    )
    cited_chunk_ids: list[str] = Field(
        default_factory=list,
        description="Exact chunk_id strings from <policy_context> that support the answer.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Groundedness confidence between 0.0 and 1.0.",
    )


class CopilotQueryResponse(BaseModel):
    """API response envelope for a Compliance Copilot query."""

    request_id: str
    sanitized_query: str
    pii_redacted_count: int
    redacted_types: list[str]
    outcome: Literal["answered", "refused", "blocked"]
    answer: str
    citations: list[Citation]
    confidence: float
    model_name: str
    latency_ms: int


class AuditLogSummary(BaseModel):
    """Read-only view of an immutable compliance copilot audit log entry."""

    id: UUID
    request_id: str
    sanitized_query: str
    answer: str = ""
    pii_redacted_count: int
    retrieved_chunk_ids: list[str]
    outcome: str
    model_name: str
    latency_ms: int
    created_at: datetime
