from battlescope_api.graph.nodes.sec_risk import (
    crude_html_to_text,
    extract_item_1a_window,
    pick_latest_10k_row,
)


def test_pick_latest_10k_prefers_newer_filing() -> None:
    filings = [
        {
            "formType": "8-K",
            "filingDate": "2025-12-01 00:00:00",
            "finalLink": "https://example.com/8k",
        },
        {
            "formType": "10-K",
            "filingDate": "2024-09-30 00:00:00",
            "finalLink": "https://example.com/old10k.htm",
        },
        {
            "formType": "10-K",
            "filingDate": "2025-10-31 00:00:00",
            "finalLink": "https://example.com/new10k.htm",
        },
    ]
    row = pick_latest_10k_row(filings)
    assert row is not None
    assert row["finalLink"] == "https://example.com/new10k.htm"


def test_pick_latest_10k_none_when_no_10k() -> None:
    assert pick_latest_10k_row([{"formType": "4", "filingDate": "2025-01-01", "finalLink": "x"}]) is None


def test_extract_item_1a_window() -> None:
    plain = (
        "PART I Item 1. Business … "
        "ITEM 1A. RISK FACTORS Our business faces competition. "
        "More risk text here. ITEM 1B. Unresolved Staff Comments"
    )
    win = extract_item_1a_window(plain)
    assert win is not None
    assert "RISK FACTORS" in win or "competition" in win
    assert "ITEM 1B" not in win


def test_crude_html_to_text_strips_tags() -> None:
    html = "<html><body><p>Hello <b>world</b></p></body></html>"
    assert crude_html_to_text(html, 1000) == "Hello world"
