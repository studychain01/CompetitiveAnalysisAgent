import type { RunSyncResponse } from "@/lib/types";

export function normPeerLabel(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, " ");
}

/**
 * Collects identifiers from `peer_research_digests.by_peer` so we can mark which
 * landscape competitors received a bounded deep-dive run (same selection as the API).
 */
export function deepDivePeerIdentifiers(run: RunSyncResponse): {
  displayNorms: Set<string>;
  tickersUpper: Set<string>;
} {
  const displayNorms = new Set<string>();
  const tickersUpper = new Set<string>();
  const digests = run.peer_research_digests;
  const by = digests && typeof digests === "object" && !Array.isArray(digests) ? (digests as Record<string, unknown>).by_peer : null;
  if (!by || typeof by !== "object" || Array.isArray(by)) {
    return { displayNorms, tickersUpper };
  }
  for (const [, raw] of Object.entries(by as Record<string, unknown>)) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) continue;
    const row = raw as Record<string, unknown>;
    const dn = typeof row.display_name === "string" ? row.display_name : "";
    if (dn.trim()) displayNorms.add(normPeerLabel(dn));
    const digest = row.digest && typeof row.digest === "object" ? (row.digest as Record<string, unknown>) : null;
    const echo = digest && typeof digest.peer_display_name === "string" ? digest.peer_display_name : "";
    if (echo.trim()) displayNorms.add(normPeerLabel(echo));
    const tk = typeof row.ticker === "string" ? row.ticker.trim().toUpperCase() : "";
    if (tk) tickersUpper.add(tk);
  }
  return { displayNorms, tickersUpper };
}

export function landscapeCompetitorHasDeepDive(run: RunSyncResponse, competitor: Record<string, unknown>): boolean {
  const { displayNorms, tickersUpper } = deepDivePeerIdentifiers(run);
  const name = typeof competitor.display_name === "string" ? normPeerLabel(competitor.display_name) : "";
  if (name && displayNorms.has(name)) return true;
  const tick = typeof competitor.ticker === "string" ? competitor.ticker.trim().toUpperCase() : "";
  if (tick && tickersUpper.has(tick)) return true;
  return false;
}
