"""
Post-intake graph node (second step after IntakeProfiler): latest 10-K Item 1A (risk factors)
→ theme bullets in ``sec_risk_dossier``.

Uses ``company_profile["earnings_call"]["symbol"]`` when set (same ticker field used for transcripts).
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from battlescope_api.graph.nodes.sec_risk_html_extract import (
    extract_item_1a_from_html,
    snap_truncation_to_word_boundary,
)
from battlescope_api.graph.state import GraphState
from battlescope_api.services.trace import append_trace_event
from battlescope_api.settings import Settings, get_settings
from battlescope_api.tools.fmp_client import FinancialModelingPrepClient
from battlescope_api.tools.http_client import create_http_client
from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)

_ITEM_1A_START = re.compile(r"\bitem\s*1\s*\.?\s*a\b", re.IGNORECASE)
_ITEM_1B = re.compile(r"\bitem\s*1\s*\.?\s*b\b", re.IGNORECASE)
_ITEM_2 = re.compile(r"\bitem\s*2\b", re.IGNORECASE)


def _is_10k_family(form_type: str | None) -> bool:
    u = (form_type or "").strip().upper()
    return u.startswith("10-K")


def _filing_sort_key(row: dict[str, Any]) -> float:
    for key in ("filingDate", "acceptedDate"):
        raw = row.get(key)
        if not raw:
            continue
        s = str(raw).strip().split()[0]
        try:
            parts = [int(x) for x in s.split("-")]
            if len(parts) == 3:
                return float(parts[0] * 10_000 + parts[1] * 100 + parts[2])
        except ValueError:
            continue
    return 0.0


def pick_latest_10k_row(filings: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Choose the most recent primary annual filing row (10-K family) with a ``finalLink``."""
    candidates = [
        f
        for f in filings
        if _is_10k_family(str(f.get("formType"))) and (f.get("finalLink") or f.get("link"))
    ]
    if not candidates:
        return None
    return max(candidates, key=_filing_sort_key)


def crude_html_to_text(html: str, max_chars: int) -> str:
    """Strip scripts/styles/tags; collapse whitespace (good enough for Item 1A search)."""
    text = html
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<head[^>]*>.*?</head>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def extract_item_1a_window(plain: str) -> str | None:
    """Slice plain text from Item 1A through Item 1B / Item 2 (exclusive), if found."""
    m = _ITEM_1A_START.search(plain)
    if not m:
        return None
    start = m.start()
    tail = plain[start:]
    ends: list[int] = []
    for pattern in (_ITEM_1B, _ITEM_2):
        mm = pattern.search(tail, pos=1)
        if mm:
            ends.append(mm.start())
    end_offset = min(ends) if ends else min(len(tail), 400_000)

    return tail[:end_offset].strip()


class SecRiskThemeBullets(BaseModel):
    """Structured output for distilling Item 1A into substantive theme bullets."""

    bullets: list[str] = Field(
        default_factory=list,
        description=(
            "8–12 bullets; each ~35–80 words: one material risk with mechanism and business consequence; "
            "paraphrase only; no buy/sell/hold or investment advice."
        ),
    )


# Closed vocabulary for second-pass UI grouping (parallel to ``risk_theme_bullets`` indices).
RISK_THEME_CATEGORY_ORDER: tuple[str, ...] = (
    "Competition",
    "Demand/Macro",
    "Supply chain",
    "Regulatory",
    "Cyber/IP",
    "Operational",
    "Financial/Liquidity",
    "Legal/Litigation",
    "People",
    "Strategy/Execution",
    "Other",
)

_CATEGORY_BY_LOWER: dict[str, str] = {c.casefold(): c for c in RISK_THEME_CATEGORY_ORDER}


class SecRiskThemeCategories(BaseModel):
    """Per-bullet UI labels from the same LLM call as categorization — do not rewrite the source bullets."""

    categories: list[str] = Field(
        default_factory=list,
        description="Exactly one category label per bullet, same count and order as the enumerated bullets.",
    )
    headlines: list[str] = Field(
        default_factory=list,
        description=(
            "Exactly one short headline per bullet (same count/order): scannable title, ~6–14 words, "
            "captures the main risk; must not contradict the bullet; not a copy-paste of the full bullet."
        ),
    )


def _normalize_risk_category_label(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    return _CATEGORY_BY_LOWER.get(s.casefold(), "Other")


def validated_risk_theme_categories(
    bullets: list[str],
    categories: list[str] | None,
) -> list[str] | None:
    """Return normalized parallel categories, or None if length mismatch or invalid."""
    if not bullets or not categories:
        return None
    if len(categories) != len(bullets):
        return None
    out: list[str] = []
    for raw in categories:
        label = _normalize_risk_category_label(str(raw))
        if not label:
            return None
        out.append(label)
    return out


_RISK_HEADLINE_MAX_CHARS = 120


def validated_risk_theme_headlines(
    bullets: list[str],
    headlines: list[str] | None,
) -> list[str] | None:
    """Return trimmed headlines (length-capped), or None if length mismatch or any empty after trim."""
    if not bullets or not headlines:
        return None
    if len(headlines) != len(bullets):
        return None
    out: list[str] = []
    for raw in headlines:
        s = str(raw).strip()
        if not s:
            return None
        if len(s) > _RISK_HEADLINE_MAX_CHARS:
            s = s[: _RISK_HEADLINE_MAX_CHARS - 1].rstrip() + "…"
        out.append(s)
    return out


def _bullets_snippet_for_label_prompt(bullets: list[str], *, max_each: int = 360) -> str:
    lines: list[str] = []
    for i, b in enumerate(bullets):
        t = b.strip()
        clip = t[:max_each] + ("…" if len(t) > max_each else "")
        lines.append(f"[{i}] {clip}")
    return "\n".join(lines)


async def _label_risk_bullet_categories(
    settings: Settings,
    bullets: list[str],
) -> tuple[list[str] | None, list[str] | None]:
    """Second LLM pass: closed-vocabulary category + short headline per bullet. On failure returns (None, None)."""
    if not bullets or not settings.openai_api_key:
        return None, None
    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_sdk_base_url,
        model=settings.openai_model,
        temperature=0.0,
    )
    structured = model.with_structured_output(SecRiskThemeCategories)
    vocab = ", ".join(RISK_THEME_CATEGORY_ORDER)
    enumerated = _bullets_snippet_for_label_prompt(bullets)
    msg = HumanMessage(
        content=(
            "## Task\n"
            "Each line below is one **risk theme bullet** (index in brackets). The bullets are **final** — "
            "do not rewrite, summarize, merge, reorder, or drop any bullet.\n\n"
            "## Output\n"
            "Return two arrays of **equal length**, matching bullets in order (indices 0.."
            f"{len(bullets) - 1}):\n"
            "1. `categories` — exactly one **closed-vocabulary** label per bullet (see allowed list).\n"
            "2. `headlines` — exactly one **short headline** per bullet for UI: scannable, plain language, "
            "roughly **6–14 words**, no leading numbering, no quotes; capture the single dominant risk; "
            "must not contradict the bullet; **do not** paste or lightly tweak the full bullet text.\n\n"
            "## Allowed category labels (exact spelling)\n"
            f"{vocab}\n\n"
            "## Bullets\n\n"
            f"{enumerated}"
        )
    )
    try:
        out = await structured.ainvoke([msg])
        raw_cats: list[str] = []
        raw_heads: list[str] = []
        if isinstance(out, SecRiskThemeCategories):
            raw_cats = [str(x) for x in out.categories]
            raw_heads = [str(x) for x in out.headlines]
        elif isinstance(out, dict):
            raw_cats = [str(x) for x in (out.get("categories") or [])]
            raw_heads = [str(x) for x in (out.get("headlines") or [])]
        cats = validated_risk_theme_categories(bullets, raw_cats)
        heads = validated_risk_theme_headlines(bullets, raw_heads)
        return cats, heads
    except Exception as exc:
        logger.warning("sec_risk_llm_categorize_failed", extra={"error": str(exc)})
        return None, None


def _heuristic_bullets_from_excerpt(excerpt: str, *, max_bullets: int = 8) -> list[str]:
    """Fallback when OpenAI is unavailable: split on sentence boundaries."""
    chunk = excerpt[:8000]
    parts = re.split(r"(?<=[.!?])\s+", chunk)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if 20 <= len(p) <= 220:
            out.append(p)
        if len(out) >= max_bullets:
            break
    return out


async def _summarize_excerpt_to_bullets(
    settings: Settings,
    excerpt: str,
) -> list[str]:
    clip = snap_truncation_to_word_boundary(
        excerpt,
        settings.sec_risk_excerpt_max_chars,
        lookback=min(1500, settings.sec_risk_excerpt_max_chars),
    )
    if not settings.openai_api_key:
        return _heuristic_bullets_from_excerpt(clip)
    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_sdk_base_url,
        model=settings.openai_model,
        temperature=0.1,
    )
    structured = model.with_structured_output(SecRiskThemeBullets)
    msg = HumanMessage(
        content=(
            "## Context\n"
            "You are helping a **competitive intelligence** pipeline (BattleScope). The excerpt below is "
            "from a U.S. public company **Form 10-K, Item 1A — Risk Factors** (SEC filing language: "
            "cautious, sometimes repetitive or legalistic).\n\n"
            "## How your output will be used\n"
            "These bullets feed **downstream agents**: (1) **competitor discovery and framing** — "
            "which other companies may be advantaged or exposed on the same axes; (2) **research "
            "priorities** — which risk themes deserve deeper web/news validation; (3) **briefings** — "
            "executives skim bullets to understand what the company itself says could hurt the business.\n\n"
            "## What to target\n"
            "- **Material, distinct risk themes** — not generic one-liners (avoid bullets that could apply "
            "to any large company with only a proper-noun swap).\n"
            "- For each theme, combine where the text allows: **what the risk is**, **why it could "
            "materialize** (mechanism, dependency, or external driver), and **how it could affect "
            "the business** (demand, cost, margin, reputation, legal/regulatory, execution, capital, "
            "technology, supply chain, etc.).\n"
            "- Prefer **specific drivers** named in the excerpt (markets, products, geographies, "
            "regulations, counterparties) over vague boilerplate.\n"
            "- Cover **several categories** across bullets when the excerpt supports it (e.g. competition, "
            "regulation, macro, operational, cyber/IP, talent, litigation, liquidity) rather than "
            "many near-duplicates.\n"
            "- **Paraphrase** in clear modern English; do not copy long phrases verbatim; do not "
            "invent facts beyond the excerpt.\n\n"
            "## Output shape\n"
            "- Produce **8–12 bullets** in the `bullets` array.\n"
            "- Each bullet should be **roughly 35–80 words** (about 2–4 sentences of substance). "
            "**Do not** reduce each theme to a single short sentence — that is too thin for downstream use.\n"
            "- No numbering or leading symbols in the string; plain prose per bullet.\n"
            "- No investment recommendations (no buy/sell/hold, no price targets).\n\n"
            "## Source excerpt (Item 1A)\n\n"
            f"{clip}"
        )
    )
    try:
        out = await structured.ainvoke([msg])
        if isinstance(out, SecRiskThemeBullets):
            return [b.strip() for b in out.bullets if b.strip()][:12]
        if isinstance(out, dict):
            raw = out.get("bullets") or []
            return [str(b).strip() for b in raw if str(b).strip()][:12]
    except Exception as exc:
        logger.warning("sec_risk_llm_summarize_failed", extra={"error": str(exc)})
    return _heuristic_bullets_from_excerpt(clip)


async def _fetch_filing_html(
    tool: ToolClient,
    url: str,
    *,
    user_agent: str,
    max_chars: int,
) -> tuple[int, str]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = await tool.request("GET", url, headers=headers, timeout=60.0)
    body = response.text or ""
    if len(body) > max_chars:
        body = body[:max_chars]
    return response.status_code, body


def _empty_dossier(
    *,
    status: str,
    symbol: str | None,
    reason: str | None = None,
    filing: dict[str, Any] | None = None,
    bullets: list[str] | None = None,
    extraction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": status,
        "symbol": symbol,
        "reason": reason,
        "filing": filing,
        "risk_theme_bullets": bullets or [],
    }
    out["extraction"] = extraction or {
        "method": "none",
        "confidence": "low",
        "notes": [],
        "start_fragment": None,
        "end_marker": None,
    }
    return out


async def run_sec_risk_pipeline(
    *,
    settings: Settings,
    symbol: str,
    tool: ToolClient,
) -> dict[str, Any]:
    sym = symbol.strip().upper()
    today = date.today()
    date_to = today.isoformat()
    date_from = (today - timedelta(days=3 * 365)).isoformat()

    fmp = FinancialModelingPrepClient(settings.fmp_api_key, tool)
    filings = await fmp.sec_filings_search_by_symbol(sym, date_from=date_from, date_to=date_to, limit=100)
    row = pick_latest_10k_row(filings)
    if row is None:
        return _empty_dossier(
            status="no_filing",
            symbol=sym,
            reason="No 10-K family filing with link found in FMP window.",
        )

    final_link = str(row.get("finalLink") or row.get("link") or "").strip()
    if not final_link.startswith("http"):
        return _empty_dossier(
            status="error",
            symbol=sym,
            reason="FMP row missing finalLink.",
            filing={"form_type": row.get("formType"), "filing_date": row.get("filingDate")},
        )

    status_code, html = await _fetch_filing_html(
        tool,
        final_link,
        user_agent=settings.sec_edgar_user_agent,
        max_chars=settings.sec_risk_filing_download_max_chars,
    )
    if status_code >= 400 or not html.strip():
        return _empty_dossier(
            status="error",
            symbol=sym,
            reason=f"SEC/filing fetch HTTP {status_code} or empty body.",
            filing={
                "form_type": row.get("formType"),
                "filing_date": row.get("filingDate"),
                "final_link": final_link,
            },
        )

    excerpt, extraction = extract_item_1a_from_html(
        html,
        max_dom_text_chars=settings.sec_risk_filing_download_max_chars,
    )
    if not excerpt:
        return _empty_dossier(
            status="partial",
            symbol=sym,
            reason="Could not locate Item 1A boundaries in filing text (format may differ).",
            filing={
                "form_type": row.get("formType"),
                "filing_date": row.get("filingDate"),
                "cik": row.get("cik"),
                "final_link": final_link,
            },
            extraction=extraction,
        )

    bullets = await _summarize_excerpt_to_bullets(settings, excerpt)
    filing_meta = {
        "form_type": row.get("formType"),
        "filing_date": row.get("filingDate"),
        "accepted_date": row.get("acceptedDate"),
        "cik": row.get("cik"),
        "final_link": final_link,
    }
    dossier_ok: dict[str, Any] = {
        "status": "ok",
        "symbol": sym,
        "reason": None,
        "filing": filing_meta,
        "risk_theme_bullets": bullets,
        "excerpt_chars": len(excerpt),
        "extraction": extraction,
    }
    if bullets:
        cats, heads = await _label_risk_bullet_categories(settings, bullets)
        if cats is not None:
            dossier_ok["risk_theme_categories"] = cats
        if heads is not None:
            dossier_ok["risk_theme_headlines"] = heads
    return dossier_ok


async def sec_risk_node(state: GraphState) -> GraphState:
    run_id = state.get("run_id", "")
    events = list(state.get("trace_events", []))
    notes = list(state.get("planner_notes", []))

    append_trace_event(events, "node_start", run_id, "SecRisk10K")

    settings = get_settings()
    profile = state.get("company_profile") or {}
    ec = profile.get("earnings_call")
    raw_symbol = ec.get("symbol") if isinstance(ec, dict) else None
    symbol = (str(raw_symbol).strip().upper() if raw_symbol else "") or None

    if not settings.fmp_api_key:
        dossier = _empty_dossier(
            status="skipped",
            symbol=symbol,
            reason="FMP_API_KEY not configured.",
        )
        notes.append("SecRisk10K skipped: FMP_API_KEY not configured.")
    elif not symbol:
        dossier = _empty_dossier(
            status="skipped",
            symbol=None,
            reason="No equity ticker on company_profile.earnings_call.symbol.",
        )
        notes.append("SecRisk10K skipped: no ticker on profile (set earnings_call.symbol after intake).")
    else:
        try:
            async with create_http_client() as raw_client:
                http_tool = ToolClient(
                    raw_client,
                    max_retries=settings.http_max_retries,
                    backoff_base_s=settings.http_backoff_base_s,
                    retryable_methods=frozenset({"GET"}),
                )
                dossier = await run_sec_risk_pipeline(settings=settings, symbol=symbol, tool=http_tool)
        except Exception as exc:
            logger.exception("sec_risk_pipeline_failed")
            dossier = _empty_dossier(
                status="error",
                symbol=symbol,
                reason=f"{type(exc).__name__}: {exc}",
            )
            notes.append(f"SecRisk10K failed ({type(exc).__name__}): {exc}")

        st = dossier.get("status")
        if st == "ok":
            n = len(dossier.get("risk_theme_bullets") or [])
            notes.append(f"SecRisk10K: distilled {n} risk-theme bullets from latest 10-K for {symbol}.")
        elif st == "no_filing":
            notes.append(f"SecRisk10K: no 10-K filing in window for {symbol}.")
        elif st == "partial":
            notes.append(f"SecRisk10K: partial — {dossier.get('reason')}")
        elif st == "error" and dossier.get("reason"):
            notes.append(f"SecRisk10K: error — {dossier.get('reason')}")

    append_trace_event(events, "node_end", run_id, "SecRisk10K")

    return {
        "sec_risk_dossier": dossier,
        "planner_notes": notes,
        "trace_events": events,
        "stage": "sec_risk",
    }


async def run_sec_risk_for_tests(state: GraphState) -> GraphState:
    """Test entrypoint mirroring ``sec_risk_node``."""
    return await sec_risk_node(state)
