"""Structured output for post-SEC competitor discovery (ReAct + tools)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SecConcernDomainRow(BaseModel):
    """Maps a home-company 10-K Item 1A theme to how a named peer relates on that axis."""

    model_config = ConfigDict(extra="ignore")

    home_sec_theme_label: str = Field(
        description="Short label or paraphrase of a risk theme from the home company's Item 1A bullets.",
    )
    home_risk_bullet_index: int | None = Field(
        default=None,
        ge=0,
        description="0-based index into risk_theme_bullets when applicable; else null.",
    )
    peer_positioning: str = Field(
        description=(
            "Why this peer is often positioned ahead, named as a rival, or more exposed on this axis, "
            "grounded in tool snippets where possible."
        ),
    )
    supporting_urls: list[str] = Field(
        default_factory=list,
        description="URLs from Tavily/News/scrape snippets that support the claim; [] only if speculative.",
    )
    speculative: bool = Field(
        default=False,
        description="True when the link to this SEC theme is inferred without direct snippet support.",
    )


class CompetitorEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    display_name: str
    ticker: str | None = None
    why_in_top_set: str = Field(description="Why this company belongs in the top 3–6 set for the target.")
    evidence_grade: str = Field(
        default="moderate",
        description="One of: strong, moderate, weak, speculative — based on corroboration in tool output.",
    )
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    sec_concern_domains: list[SecConcernDomainRow] = Field(
        default_factory=list,
        description="At least one row recommended when SEC bullets exist; tie peers to home risk themes.",
    )


class CompetitorLandscapeLlm(BaseModel):
    """Root schema for create_react_agent response_format."""

    model_config = ConfigDict(extra="ignore")

    target_company_context_note: str = Field(
        default="",
        description=(
            "One short line: how you used profile + SEC bullets + tools (for audit). "
            "If fewer than 3 competitors, explain what queries were tried and why evidence was insufficient."
        ),
    )
    competitors: list[CompetitorEntry] = Field(
        default_factory=list,
        max_length=6,
        description="3–6 distinct named competitors (not the target company).",
    )

    def as_state_dict(self) -> dict[str, Any]:
        return self.model_dump()


def empty_competitor_landscape(*, status: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "competitors": [],
        "degraded": False,
        "target_company_context_note": None,
    }


def finalize_landscape_from_llm(model: CompetitorLandscapeLlm) -> dict[str, Any]:
    """
    Dedupe by display name, cap at 6, set degraded when fewer than 3 competitors after cleanup.
    """
    seen: set[str] = set()
    out_list: list[CompetitorEntry] = []
    for c in model.competitors:
        key = c.display_name.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out_list.append(c)
        if len(out_list) >= 6:
            break

    degraded = len(out_list) < 3
    status = "ok" if not degraded and out_list else ("partial" if out_list else "empty")

    return {
        "status": status,
        "reason": None if not degraded else f"Only {len(out_list)} distinct competitor(s) after dedupe; need 3–6.",
        "degraded": degraded,
        "target_company_context_note": model.target_company_context_note or None,
        "competitors": [c.model_dump() for c in out_list],
    }
