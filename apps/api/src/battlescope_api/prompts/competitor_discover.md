# CompetitorDiscoverer

Objective: return **5–6** competitor candidates when evidence allows (**minimum 3**), each with provenance URLs/snippets.

**Pipeline:** the server runs **Tavily first** with `top 10 competitors of <target>` (max 10 results). The ReAct agent **narrows** that pool with tools and returns a **final 3–6** list (prefer **5–6**).

Rules: every candidate must cite at least one search result URL.

On low evidence: broaden queries; label adjacent-market candidates.