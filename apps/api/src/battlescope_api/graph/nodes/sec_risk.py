"""
Post-intake graph node (second step after IntakeProfiler): latest 10-K Item 1A (risk factors)
→ theme bullets in ``sec_risk_dossier``.

Uses ``company_profile["earnings_call"]["symbol"]`` when set (same ticker field used for transcripts).

If Item 1A cannot be produced (private issuer, missing FMP/ticker, fetch/extract failure), a **web fallback**
(Tavily and/or Firecrawl + LLM) may fill ``risk_theme_bullets`` with ``risk_theme_source: "web_tools"``.
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
from battlescope_api.tools.firecrawl_client import FirecrawlClient
from battlescope_api.tools.fmp_client import FinancialModelingPrepClient
from battlescope_api.tools.http_client import create_http_client
from battlescope_api.tools.tavily_client import TavilyClient
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


_WEB_FALLBACK_PACK_MAX_CHARS = 28_000


def _entity_display_label(profile: dict[str, Any], state: GraphState) -> str:
    name = profile.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    cn = state.get("company_name")
    if isinstance(cn, str) and cn.strip():
        return cn.strip()
    return ""


def _format_tavily_block_for_pack(payload: dict[str, Any], *, snippet_max: int = 650) -> str:
    lines: list[str] = []
    for idx, item in enumerate(payload.get("results") or [], start=1):
        title = item.get("title") or ""
        url = item.get("url") or ""
        content = (item.get("content") or "").strip()
        if len(content) > snippet_max:
            content = content[: snippet_max - 1].rstrip() + "…"
        lines.append(f"{idx}. {title}\n   URL: {url}\n   Snippet: {content}")
    return "\n\n".join(lines) if lines else ""


def _firecrawl_markdown_from_payload(payload: dict[str, Any]) -> str:
    if payload.get("success") is False:
        return ""
    data = payload.get("data") or {}
    md = data.get("markdown") or payload.get("markdown") or ""
    return str(md).strip()


def _clip_web_pack(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 24] + "\n...[web pack truncated]..."


async def _gather_web_risk_pack(
    *,
    settings: Settings,
    profile: dict[str, Any],
    state: GraphState,
    http_tool: ToolClient,
) -> tuple[str, list[str]]:
    """Tavily snippets + optional Firecrawl homepage; returns (combined text, source URLs)."""
    label = _entity_display_label(profile, state) or "the target company"
    chunks: list[str] = []
    urls: list[str] = []

    if settings.tavily_api_key:
        tavily = TavilyClient(settings.tavily_api_key, http_tool)
        queries = [
            f'"{label}" company risks challenges business',
            f'"{label}" competition market regulatory industry',
        ]
        sym = profile.get("earnings_call") if isinstance(profile.get("earnings_call"), dict) else {}
        raw_sym = sym.get("symbol") if isinstance(sym, dict) else None
        if isinstance(raw_sym, str) and raw_sym.strip():
            t = raw_sym.strip().upper()
            queries.append(f"{t} stock risks analyst concerns")
        for q in queries:
            try:
                payload = await tavily.search(q, max_results=5)
                block = _format_tavily_block_for_pack(payload)
                if block.strip():
                    chunks.append(f"## Tavily: {q}\n\n{block}")
                for item in payload.get("results") or []:
                    u = item.get("url")
                    if isinstance(u, str) and u.strip():
                        urls.append(u.strip())
            except Exception as exc:
                logger.warning("sec_risk_web_tavily_failed", extra={"query": q[:80], "error": str(exc)})

    if settings.firecrawl_api_key:
        raw_u = state.get("company_url_normalized")
        u = raw_u.strip() if isinstance(raw_u, str) else ""
        if u.startswith(("http://", "https://")):
            try:
                fc = FirecrawlClient(settings.firecrawl_api_key, http_tool)
                payload = await fc.scrape_url(u)
                md = _firecrawl_markdown_from_payload(payload)
                if md:
                    cap = min(12_000, _WEB_FALLBACK_PACK_MAX_CHARS // 2)
                    chunks.append(f"## Firecrawl homepage ({u})\n\n{md[:cap]}")
                    urls.append(u)
            except Exception as exc:
                logger.warning("sec_risk_web_firecrawl_failed", extra={"url": u[:120], "error": str(exc)})

    pack = _clip_web_pack("\n\n".join(chunks), _WEB_FALLBACK_PACK_MAX_CHARS)
    dedup_urls: list[str] = []
    seen: set[str] = set()
    for x in urls:
        if x not in seen:
            seen.add(x)
            dedup_urls.append(x)
    return pack, dedup_urls[:30]


async def _summarize_web_pack_to_bullets(
    settings: Settings,
    pack: str,
    entity_label: str,
) -> list[str]:
    clip = snap_truncation_to_word_boundary(
        pack,
        min(len(pack), settings.sec_risk_excerpt_max_chars + 8000),
        lookback=min(2000, settings.sec_risk_excerpt_max_chars),
    )
    if not clip.strip():
        return []
    if not settings.openai_api_key:
        return _heuristic_bullets_from_excerpt(clip, max_bullets=8)
    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_sdk_base_url,
        model=settings.openai_model,
        temperature=0.15,
    )
    structured = model.with_structured_output(SecRiskThemeBullets)
    label = entity_label or "the target company"
    msg = HumanMessage(
        content=(
            "## Context\n"
            "You are helping a **competitive intelligence** pipeline (BattleScope). The text below is **NOT** "
            "from an SEC filing. It is a **clip of public web snippets and/or a scraped company page** "
            "(search results, news, marketing copy, blogs). It may be incomplete, promotional, or wrong.\n\n"
            "## Task\n"
            f"From this material only, infer **material business risk themes** for **{label}** as a going concern: "
            "competition, demand, regulation, operations, supply chain, cyber, talent, financing, litigation, "
            "geography, technology, etc. **Do not** claim these are SEC “Risk Factors” or Item 1A language.\n"
            "- **Paraphrase**; do not invent facts not supported by the clip.\n"
            "- If the clip is thin, emit **fewer** substantive bullets rather than padding.\n"
            "- No buy/sell/hold or investment advice.\n\n"
            "## Output shape\n"
            "- Produce **6–10 bullets** in `bullets` (cap at 10).\n"
            "- Each bullet **roughly 35–80 words**, plain prose, no numbering.\n\n"
            "## Web clip\n\n"
            f"{clip}"
        )
    )
    try:
        out = await structured.ainvoke([msg])
        if isinstance(out, SecRiskThemeBullets):
            return [b.strip() for b in out.bullets if b.strip()][:10]
        if isinstance(out, dict):
            raw = out.get("bullets") or []
            return [str(b).strip() for b in raw if str(b).strip()][:10]
    except Exception as exc:
        logger.warning("sec_risk_web_summarize_failed", extra={"error": str(exc)})
    return _heuristic_bullets_from_excerpt(clip, max_bullets=8)


def _dossier_from_web_fallback(
    prior: dict[str, Any],
    *,
    bullets: list[str],
    categories: list[str] | None,
    headlines: list[str] | None,
    source_urls: list[str],
) -> dict[str, Any]:
    pri_status = str(prior.get("status") or "")
    pri_reason = prior.get("reason")
    pri_sym = prior.get("symbol")
    tail = f" Original SEC path note: {pri_reason}" if pri_reason else ""
    reason = (
        f"SEC Item 1A was not available ({pri_status}). "
        f"Risk themes below are **inferred from public web sources** (Tavily/Firecrawl), not 10-K filing text.{tail}"
    )
    out: dict[str, Any] = {
        "status": "ok",
        "symbol": pri_sym,
        "reason": reason[:2500],
        "filing": None,
        "risk_theme_bullets": bullets,
        "risk_theme_source": "web_tools",
        "prior_sec_attempt": {"status": pri_status, "reason": pri_reason, "symbol": pri_sym},
        "web_source_urls": source_urls[:25],
        "extraction": {
            "method": "web_tools",
            "confidence": "low",
            "notes": [
                "risk_theme_bullets produced from Tavily search snippets and/or Firecrawl homepage markdown.",
            ],
            "start_fragment": None,
            "end_marker": None,
        },
    }
    if categories:
        out["risk_theme_categories"] = categories
    if headlines:
        out["risk_theme_headlines"] = headlines
    return out


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

    pri_bullets = list(dossier.get("risk_theme_bullets") or [])
    pri_status = str(dossier.get("status") or "")
    if (
        not pri_bullets
        and settings.openai_api_key
        and (settings.tavily_api_key or settings.firecrawl_api_key)
        and pri_status in ("no_filing", "skipped", "error", "partial")
    ):
        prof = profile if isinstance(profile, dict) else {}
        try:
            async with create_http_client() as raw_client:
                web_tool = ToolClient(
                    raw_client,
                    max_retries=settings.http_max_retries,
                    backoff_base_s=settings.http_backoff_base_s,
                    retryable_methods=frozenset({"GET", "POST"}),
                )
                pack, source_urls = await _gather_web_risk_pack(
                    settings=settings,
                    profile=prof,
                    state=state,
                    http_tool=web_tool,
                )
            if pack.strip():
                label = _entity_display_label(prof, state)
                fb_bullets = await _summarize_web_pack_to_bullets(settings, pack, label)
                if fb_bullets:
                    cats, heads = await _label_risk_bullet_categories(settings, fb_bullets)
                    dossier = _dossier_from_web_fallback(
                        dossier,
                        bullets=fb_bullets,
                        categories=cats,
                        headlines=heads,
                        source_urls=source_urls,
                    )
                    notes.append(
                        f"SecRisk10K: web fallback produced {len(fb_bullets)} theme(s) "
                        "(Tavily/Firecrawl; not SEC Item 1A)."
                    )
                    logger.info(
                        "sec_risk_web_fallback_applied",
                        extra={"bullet_count": len(fb_bullets), "prior_status": pri_status},
                    )
                else:
                    notes.append("SecRisk10K: web fallback produced no bullets after LLM pass.")
            else:
                notes.append("SecRisk10K: web fallback skipped (no Tavily/Firecrawl text retrieved).")
        except Exception as exc:
            logger.warning("sec_risk_web_fallback_failed", extra={"error": str(exc)})
            notes.append(f"SecRisk10K: web fallback failed ({type(exc).__name__}): {exc}")

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
