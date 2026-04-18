"""Structured output for deep peer research (single competitor per ReAct run)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AheadAxis(BaseModel):
    """One axis where the peer is materially ahead or differentiated vs the market."""

    model_config = ConfigDict(extra="ignore")

    axis: str = Field(
        description=(
            "Short label, e.g. distribution, integrations, compliance, pricing, brand, performance, ecosystem."
        ),
    )
    rationale: str = Field(description="Why this axis matters for the peer; grounded in sources where possible.")
    source_urls: list[str] = Field(
        default_factory=list,
        description="URLs from Tavily/News/scrape that support this axis.",
    )
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class PowerUserHypothesis(BaseModel):
    """Hypothesis about who the peer's strongest / most loyal users are (no predatory tactics)."""

    model_config = ConfigDict(extra="ignore")

    segment_label: str = Field(description="e.g. mid-market ops teams, security-conscious enterprises.")
    jobs_to_be_done: list[str] = Field(
        default_factory=list,
        description="Concrete jobs this segment hires the peer to do (keep concise).",
    )
    signals: list[str] = Field(
        default_factory=list,
        description="Observable signals from product, pricing, docs, community, or press (evidence-limited).",
    )


class PeerResearchDigestLlm(BaseModel):
    """Root schema for create_react_agent response_format (one peer per invocation)."""

    model_config = ConfigDict(extra="ignore")

    peer_display_name: str = Field(default="", description="Echo canonical peer name from the brief.")
    ahead_axes: list[AheadAxis] = Field(
        default_factory=list,
        max_length=2,
        description="1–2 axes where the peer leads or is strongly differentiated; cite URLs.",
    )
    power_user_hypothesis: PowerUserHypothesis = Field(
        default_factory=PowerUserHypothesis,
        description="Who power users likely are and why.",
    )
    evidence_notes: str = Field(
        default="",
        description="Brief note on source quality, gaps, or conflicts in snippets.",
    )
    overall_confidence: float = Field(default=0.6, ge=0.0, le=1.0)

    def as_state_dict(self) -> dict[str, Any]:
        return self.model_dump()


def empty_peer_research_payload(*, status: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "by_peer": {},
    }
