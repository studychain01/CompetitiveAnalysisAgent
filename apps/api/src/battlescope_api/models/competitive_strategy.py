"""Structured competitive strategy (terminal synthesis over intake + SEC + peers)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InputQuality(BaseModel):
    model_config = ConfigDict(extra="ignore")

    competitor_landscape_degraded: bool = False
    competitor_count: int = 0
    peer_digest_rows: int = 0
    peer_digests_ok_count: int = 0
    notes: str = Field(default="", description="Caveats about missing or partial upstream research.")


class AdvantageGapRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    peer_name: str
    axis_or_advantage: str
    peer_evidence_summary: str = Field(description="What the peer leads on; tie to digest/landscape when possible.")
    home_gap: str = Field(description="Where the target appears weaker or exposed vs that axis.")
    source_urls: list[str] = Field(
        default_factory=list,
        description="URLs copied from peer digests or competitor_landscape only; [] if none.",
    )
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class PrioritizedMove(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rank: int = Field(ge=1, description="1 = highest priority.")
    title: str
    rationale: str
    horizon: str = Field(description="One of: short, long (short ~0–90d, long ~6–24m).")
    effort: str = Field(description="One of: low_hanging, medium, heavy.")
    risk_to_home: str = Field(default="", description="How this interacts with home risks (Item 1A / profile).")
    owner_hint: str = Field(
        default="",
        description="e.g. product, sales, marketing, partnerships, customer_success.",
    )


class HorizonPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    horizon_label: str = Field(description="Human-readable label, e.g. 0–90 days.")
    bullets: list[str] = Field(
        default_factory=list,
        description="Concrete, scannable actions (no wall of text per bullet).",
    )


class PeerStrategyDeepDive(BaseModel):
    """Home vs one deep-researched peer: position and reconciliation paths."""

    model_config = ConfigDict(extra="ignore")

    peer_name: str = Field(description="Must match a deep-research peer (see packed `deep_research_peer_names`).")
    where_home_stands: str = Field(
        description="2–5 sentences: how home compares to this peer (strengths, gaps, exposure), grounded in digests/landscape.",
    )
    short_term_reconciliation: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="0–90d concrete steps for home given this rivalry; 3–5 bullets when possible.",
    )
    long_term_reconciliation: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="6–24m structural moves to close the gap or defend; 2–5 bullets when possible.",
    )
    watchouts: str = Field(
        default="",
        description="Risks, constraints, or SEC themes that interact with this matchup.",
    )
    source_urls: list[str] = Field(
        default_factory=list,
        description="URLs copied from peer digests or competitor_landscape only; [] if none.",
    )


class CompetitiveStrategyLlm(BaseModel):
    """Root schema for final strategy structured output."""

    model_config = ConfigDict(extra="ignore")

    executive_summary: str = Field(
        default="",
        description="Short rollup for Overview tab (2–4 sentences); Strategy uses per-peer deep dives instead.",
    )
    peer_deep_dives: list[PeerStrategyDeepDive] = Field(
        default_factory=list,
        max_length=3,
        description="One entry per deep-research peer (max 3), same order as `deep_research_peer_names` in the pack.",
    )
    advantage_gap_matrix: list[AdvantageGapRow] = Field(default_factory=list)
    prioritized_moves: list[PrioritizedMove] = Field(default_factory=list)
    short_term_plan: HorizonPlan = Field(
        default_factory=lambda: HorizonPlan(horizon_label="0–90 days", bullets=[]),
    )
    long_term_plan: HorizonPlan = Field(
        default_factory=lambda: HorizonPlan(horizon_label="6–24 months", bullets=[]),
    )
    low_hanging_fruits: list[str] = Field(default_factory=list, description="Quick wins; each one line when possible.")
    long_term_targets: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(
        default_factory=list,
        description="Symmetric fights or bets to avoid given evidence.",
    )
    input_quality: InputQuality = Field(default_factory=InputQuality)

    def as_state_dict(self) -> dict[str, Any]:
        return self.model_dump()


class StrategyFollowupPrecursor(BaseModel):
    """Phase-1 output when optional Tavily follow-up is enabled (max 2 queries)."""

    model_config = ConfigDict(extra="ignore")

    followup_queries: list[str] = Field(
        default_factory=list,
        max_length=2,
        description="At most 2 focused Tavily queries; empty if context is sufficient.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="What remains uncertain without live search.",
    )


def empty_competitive_strategy(*, status: str, reason: str | None = None) -> dict[str, Any]:
    base = CompetitiveStrategyLlm().model_dump()
    base["status"] = status
    base["reason"] = reason
    return base


def wrap_strategy_result(model: CompetitiveStrategyLlm, *, status: str = "ok", reason: str | None = None) -> dict[str, Any]:
    out = model.model_dump()
    out["status"] = status
    out["reason"] = reason
    return out
