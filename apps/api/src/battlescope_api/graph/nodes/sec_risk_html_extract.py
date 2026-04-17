"""
HTML-first extraction of 10-K Item 1A (Risk Factors) with TOC/anchor heuristics and regex fallback.

Used by ``sec_risk_node`` (post-intake). Downstream consumers should read ``extraction`` metadata
(method + confidence) on ``sec_risk_dossier``.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

# DOM walk excerpts shorter than this are retried with flattened-regex (thin / broken sections).
_MIN_DOM_EXCERPT_CHARS = 50


def snap_truncation_to_word_boundary(
    text: str,
    max_len: int,
    *,
    lookback: int = 900,
) -> str:
    """
    Return a prefix of ``text`` with length at most ``max_len``, avoiding a hard cut mid-word.

    Rewinds within the last ``lookback`` characters (then the full prefix) to the previous
    whitespace boundary. Falls back to ``text[:max_len]`` only if no break exists.
    """
    if max_len <= 0:
        return ""
    if not text or len(text) <= max_len:
        return text
    head = text[:max_len]
    lb = min(lookback, max_len)
    window_start = max(0, max_len - lb)
    window = head[window_start:]
    for i in range(len(window) - 1, -1, -1):
        if window[i].isspace():
            return head[: window_start + i].rstrip()
    for i in range(len(head) - 1, -1, -1):
        if head[i].isspace():
            return head[:i].rstrip()
    return head


_ITEM_1A = re.compile(r"\bitem\s*1\s*\.?\s*a\b", re.IGNORECASE)
_ITEM_1B = re.compile(r"\bitem\s*1\s*\.?\s*b\b", re.IGNORECASE)
_ITEM_2 = re.compile(r"\bitem\s*2\b", re.IGNORECASE)
_ID_CANDIDATE = re.compile(
    r"(?i)(item[_\-.]?1[_\-.]?a|risk[_\-.]?factors|^ia[_\-.]?\d+|item1a)"
)


def _toc_row_suggests_item_1a(row_txt: str) -> bool:
    if _ITEM_1A.search(row_txt):
        return True
    if re.search(r"(?i)risk\s*factors", row_txt) and re.search(r"(?i)1\s*\.?\s*a", row_txt):
        return True
    return False


def _norm_fragment(href: str) -> str | None:
    if not href or not href.startswith("#"):
        return None
    frag = href[1:].strip()
    if not frag or frag.startswith("http"):
        return None
    return frag.split("#")[-1]


def _resolve_fragment(soup: BeautifulSoup, frag: str) -> Tag | None:
    if not frag:
        return None
    # Exact id (HTML5 lowercases ids in the DOM for lookup in many parsers)
    node = soup.find(id=frag)
    if isinstance(node, Tag):
        return node
    for fid in (frag, frag.lower(), frag.upper()):
        node = soup.find(id=fid)
        if isinstance(node, Tag):
            return node
    for nm in (frag, frag.lower(), frag.upper()):
        node = soup.find(attrs={"name": nm})
        if isinstance(node, Tag):
            return node
    return None


def _find_start_via_toc_anchor(soup: BeautifulSoup) -> tuple[Tag | None, str | None]:
    """TOC row linking to #fragment that points to Item 1A / Risk Factors."""
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "")
        frag = _norm_fragment(href.strip())
        if not frag:
            continue
        row_txt = ""
        parent = a.parent
        for _ in range(4):
            if parent is None:
                break
            row_txt += " " + parent.get_text(" ", strip=True)
            parent = parent.parent
        row_txt = row_txt.strip()
        if not _toc_row_suggests_item_1a(row_txt):
            continue
        target = _resolve_fragment(soup, frag)
        if isinstance(target, Tag):
            return target, frag
    return None, None


def _find_start_via_dom_id(soup: BeautifulSoup) -> tuple[Tag | None, str | None]:
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        tid = tag.get("id")
        if tid and isinstance(tid, str) and _ID_CANDIDATE.search(tid):
            return tag, tid
        nm = tag.get("name")
        if nm and isinstance(nm, str) and _ID_CANDIDATE.search(nm):
            return tag, nm
    return None, None


def _find_start_via_header_text(soup: BeautifulSoup) -> tuple[Tag | None, str | None]:
    """Locate a visible header line for Item 1A (not necessarily unique)."""
    for tag in soup.find_all(("b", "strong", "font", "p", "div", "span", "td")):
        if not isinstance(tag, Tag):
            continue
        text = tag.get_text(" ", strip=True)
        if not text or len(text) > 400:
            continue
        if _ITEM_1A.search(text) and re.search(r"(?i)risk|factor", text):
            return tag, None
        if re.match(r"(?is)^\s*item\s*1\s*\.?\s*a\.?\s*$", text):
            return tag, None
    return None, None


def _collect_text_until_item_end(
    start_tag: Tag,
    *,
    max_chars: int,
    skip_header_chars: int = 120,
) -> tuple[str, str | None, list[str]]:
    """
    Walk document order after ``start_tag``, accumulating text until Item 1B / Item 2
    appears at a plausible section boundary (search window from skip_header_chars onward).
    """
    notes: list[str] = []
    buf = ""
    end_marker: str | None = None

    for text_node in start_tag.find_all_next(string=True):
        if len(buf) >= max_chars:
            buf = snap_truncation_to_word_boundary(buf, max_chars, lookback=min(1200, max_chars))
            notes.append("truncated_max_chars_during_dom_walk")
            break
        parent = text_node.parent
        if not isinstance(parent, Tag):
            continue
        if parent.name in ("script", "style", "noscript"):
            continue
        s = str(text_node)
        if not s or not s.strip():
            continue
        buf += (" " if buf else "") + s.strip()
        if len(buf) > max_chars:
            buf = snap_truncation_to_word_boundary(buf, max_chars, lookback=min(1200, max_chars))
            notes.append("truncated_max_chars_during_dom_walk")
            break
        search_from = min(skip_header_chars, max(0, len(buf) - 500))
        tail = buf[search_from:]
        m1b = _ITEM_1B.search(tail)
        m2 = _ITEM_2.search(tail)
        candidates: list[tuple[str, int, Any]] = []
        if m1b:
            candidates.append(("item_1b", search_from + m1b.start(), m1b))
        if m2:
            candidates.append(("item_2", search_from + m2.start(), m2))
        if candidates:
            name, idx, _m = min(candidates, key=lambda x: x[1])
            buf = buf[:idx].strip()
            end_marker = name
            break

    if not end_marker:
        notes.append("end_marker_not_found_used_full_walk_buffer")

    return buf.strip(), end_marker, notes


def _confidence_for(method: str, *, end_marker: str | None, notes: list[str]) -> str:
    if method == "regex_fallback":
        return "low"
    if end_marker and "truncated" not in " ".join(notes):
        if method == "toc_anchor":
            return "high"
        if method in ("dom_id", "header_text"):
            return "medium"
    if method == "toc_anchor":
        return "medium"
    if method in ("dom_id", "header_text"):
        return "medium-low"
    return "low"


def extract_item_1a_from_html(
    html: str,
    *,
    max_dom_text_chars: int = 500_000,
) -> tuple[str | None, dict[str, Any]]:
    """
    Return ``(excerpt_plain_text_or_none, extraction_meta)``.

    ``extraction_meta`` keys: ``method``, ``confidence``, ``notes`` (list[str]),
    optional ``start_fragment``, ``end_marker``.
    """
    meta: dict[str, Any] = {
        "method": "none",
        "confidence": "low",
        "notes": [],
        "start_fragment": None,
        "end_marker": None,
    }
    if not (html or "").strip():
        meta["notes"].append("empty_html")
        return None, meta

    soup = BeautifulSoup(html, "html.parser")

    start: Tag | None = None
    method = "regex_fallback"
    frag: str | None = None
    dom_body_len = 0

    t_node, t_frag = _find_start_via_toc_anchor(soup)
    if t_node is not None:
        start, method, frag = t_node, "toc_anchor", t_frag
        meta["notes"].append("start_resolved_via_toc_anchor")
    else:
        d_node, d_frag = _find_start_via_dom_id(soup)
        if d_node is not None:
            start, method, frag = d_node, "dom_id", d_frag
            meta["notes"].append("start_resolved_via_dom_id_or_name")
        else:
            h_node, _ = _find_start_via_header_text(soup)
            if h_node is not None:
                start, method = h_node, "header_text"
                meta["notes"].append("start_resolved_via_header_text")

    if start is not None:
        meta["method"] = method
        meta["start_fragment"] = frag
        body, end_marker, walk_notes = _collect_text_until_item_end(
            start, max_chars=max_dom_text_chars
        )
        meta["end_marker"] = end_marker
        meta["notes"].extend(walk_notes)
        body = re.sub(r"\s+", " ", body).strip()
        dom_body_len = len(body)
        if dom_body_len >= _MIN_DOM_EXCERPT_CHARS:
            meta["confidence"] = _confidence_for(method, end_marker=end_marker, notes=meta["notes"])
            return body, meta
        meta["notes"].append("dom_excerpt_too_short_retry_regex")

    # Regex fallback on flattened text (legacy behavior)
    if start is None:
        meta["notes"].append("dom_methods_failed_using_flat_regex")
    else:
        meta["notes"].append("regex_replaced_short_or_missing_dom_excerpt")
    meta["method"] = "regex_fallback"
    meta["start_fragment"] = None if start is None else frag
    plain = _flatten_html_to_plain(html, max_chars=max_dom_text_chars)
    excerpt = _extract_item_1a_window_regex(plain)
    if excerpt:
        meta["end_marker"] = _regex_excerpt_end_marker(excerpt)
        meta["confidence"] = "low"
        return excerpt.strip(), meta
    meta["notes"].append("regex_fallback_found_no_item_1a")
    return None, meta


def _flatten_html_to_plain(html: str, *, max_chars: int) -> str:
    text = html
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<head[^>]*>.*?</head>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _extract_item_1a_window_regex(plain: str) -> str | None:
    m = _ITEM_1A.search(plain)
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


def _regex_excerpt_end_marker(excerpt: str) -> str | None:
    """Which end pattern appears in the regex-derived excerpt (after skipping header)."""
    tail = excerpt[min(200, len(excerpt) // 4) :]
    if _ITEM_1B.search(tail):
        return "item_1b"
    if _ITEM_2.search(tail):
        return "item_2"
    if len(excerpt) >= 350_000:
        return "truncated_cap"
    return None
