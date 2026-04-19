# CompetitorDiscoverer

Objective: return **3–5 high-quality, same-industry** competitor candidates (**minimum 3** when evidence allows), each with provenance URLs/snippets.

**Pipeline:** the server runs **Tavily** first with a broad peer query (max 10 results). The ReAct agent **filters out wrong-sector noise**, then **verifies one candidate at a time** with tools and returns a **final 3–5** list—**not** bulk-copied megacaps (e.g. not Apple/Samsung for an aerospace OEM).

Rules: every candidate must cite at least one search result URL.

On low evidence: broaden queries; label adjacent-market candidates.
