from pydantic import BaseModel, ConfigDict, Field


class EarningsCallBlock(BaseModel):
    """All earnings-call–related profile fields in one place (symbol, quarter, derived bullets)."""

    model_config = ConfigDict(extra="ignore")

    symbol: str | None = Field(
        default=None,
        description="Equity ticker if earnings_call_transcript was used; else null.",
    )
    quarter: str | None = Field(
        default=None,
        description="Fiscal quarter YYYYQn if transcript tool was used; else null.",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description=(
            "Short bullets (0–10): strengths or advantages grounded in evidence; "
            "prioritize management-stated themes when earnings_call_transcript was used."
        ),
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description=(
            "Short bullets (0–10): risks, weaknesses, or headwinds grounded in evidence "
            "(e.g. guidance, competitive pressure, cost). Use [] if none identified."
        ),
    )


class CompanyProfileLlm(BaseModel):
    """Structured company profile produced by IntakeProfiler (LLM path)."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(description="Canonical company display name")
    category: str = Field(default="unknown")
    buyer: str = Field(default="unknown")
    business_model: str = Field(default="unknown")
    summary: str = Field(default="")
    uncertainties: list[str] = Field(default_factory=list)
    primary_domain: str | None = None
    category_alternatives: list[str] = Field(default_factory=list)
    profile_confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    earnings_call: EarningsCallBlock = Field(
        default_factory=EarningsCallBlock,
        description=(
            "One object: ticker and quarter when transcript tool was used (else null), "
            "plus strengths/weaknesses bullets grounded in all research (prioritize call when used)."
        ),
    )

    def as_state_dict(self) -> dict:
        return self.model_dump()
