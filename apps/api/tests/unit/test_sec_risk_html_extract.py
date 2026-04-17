import re

from battlescope_api.graph.nodes.sec_risk_html_extract import (
    extract_item_1a_from_html,
    snap_truncation_to_word_boundary,
)


def test_extract_via_toc_anchor_high_confidence() -> None:
    html = """
    <html><body>
    <table>
      <tr><td><a href="#riskfactors">Item 1A Risk Factors</a></td></tr>
    </table>
    <div id="riskfactors">ITEM 1A RISK FACTORS Alpha beta competition is intense.
    Gamma delta regulatory matters exist. ITEM 1B Unresolved staff comments</div>
    </body></html>
    """
    excerpt, meta = extract_item_1a_from_html(html, max_dom_text_chars=50_000)
    assert excerpt is not None
    assert "competition" in excerpt.lower()
    assert "ITEM 1B" not in excerpt
    assert meta["method"] == "toc_anchor"
    assert meta["confidence"] == "high"
    assert meta["end_marker"] == "item_1b"


def test_extract_via_dom_id() -> None:
    html = """
    <html><body>
    <div id="item1a">Item 1A Risk Factors First risk sentence. Second risk sentence here.
    ITEM 1B end</div>
    </body></html>
    """
    excerpt, meta = extract_item_1a_from_html(html, max_dom_text_chars=50_000)
    assert excerpt is not None
    assert meta["method"] == "dom_id"
    assert meta["confidence"] in ("high", "medium", "medium-low")


def test_snap_truncation_avoids_mid_word_cut() -> None:
    base = "Competition has been particularly intense as competitors have aggressive plans. "
    text = base * 30  # long enough to truncate inside a later "aggressive"
    max_len = len(text) - 25
    cut = snap_truncation_to_word_boundary(text, max_len, lookback=900)
    assert len(cut) <= max_len
    assert not cut.endswith("agg")
    assert not re.search(r"(?i)(agg|aggressi|aggressiv)$", cut.rstrip())


def test_regex_fallback_when_no_dom_start() -> None:
    plain_wrapped = (
        "<html><body>No anchors. Item 1A Risk Factors Sole paragraph about macro risk. "
        "ITEM 1B done</body></html>"
    )
    excerpt, meta = extract_item_1a_from_html(plain_wrapped, max_dom_text_chars=50_000)
    assert excerpt is not None
    assert "macro" in excerpt.lower()
    assert meta["method"] == "regex_fallback"
    assert meta["confidence"] == "low"
