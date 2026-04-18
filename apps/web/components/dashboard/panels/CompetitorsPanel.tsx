import type { RunSyncResponse } from "@/lib/types";

type Props = {
  run: RunSyncResponse;
};

export function CompetitorsPanel({ run }: Props) {
  const L = run.competitor_landscape || {};
  const status = typeof L.status === "string" ? L.status : "";
  const competitors = Array.isArray(L.competitors) ? (L.competitors as Record<string, unknown>[]) : [];
  const degraded = Boolean(L.degraded);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {(degraded || status === "partial") && (
        <div className="rounded-lg border-l-4 border-warning bg-warning/10 px-4 py-3 text-sm text-fg">
          <p className="font-medium text-warning">Competitor landscape partial or degraded</p>
          {status ? <p className="mt-1 font-mono text-xs text-muted">status: {status}</p> : null}
        </div>
      )}

      {competitors.length === 0 ? (
        <p className="text-sm text-muted">No competitors in landscape.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {competitors.map((c, idx) => {
            const name = typeof c.display_name === "string" ? c.display_name : `Competitor ${idx + 1}`;
            const ticker = typeof c.ticker === "string" ? c.ticker : "";
            const why = typeof c.why_in_top_set === "string" ? c.why_in_top_set : "";
            const grade = typeof c.evidence_grade === "string" ? c.evidence_grade : "";
            const domains = Array.isArray(c.sec_concern_domains)
              ? (c.sec_concern_domains as Record<string, unknown>[])
              : [];

            return (
              <article
                key={idx}
                className="rounded-xl border border-border bg-surface-elevated p-4 shadow-sm"
              >
                <header className="border-b border-border pb-3">
                  <h3 className="text-lg font-semibold text-fg">{name}</h3>
                  {ticker ? <p className="font-mono text-xs text-muted">{ticker}</p> : null}
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    {grade ? (
                      <span className="rounded bg-surface px-2 py-0.5 text-muted">evidence: {grade}</span>
                    ) : null}
                  </div>
                </header>
                {why ? <p className="mt-3 text-sm leading-relaxed text-muted">{why}</p> : null}

                {domains.length > 0 ? (
                  <div className="mt-4 space-y-3">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-subtle">SEC concern domains</h4>
                    <ul className="space-y-3">
                      {domains.map((row, j) => {
                        const label =
                          typeof row.home_sec_theme_label === "string" ? row.home_sec_theme_label : "";
                        const pos =
                          typeof row.peer_positioning === "string" ? row.peer_positioning : "";
                        const urls = Array.isArray(row.supporting_urls)
                          ? (row.supporting_urls as string[])
                          : [];
                        const speculative = Boolean(row.speculative);

                        return (
                          <li
                            key={j}
                            className={`rounded-md border p-3 text-sm ${
                              speculative ? "border-danger/40 bg-danger/5" : "border-border bg-surface"
                            }`}
                          >
                            {speculative ? (
                              <span className="mb-2 inline-block rounded bg-danger/15 px-1.5 py-0.5 text-[10px] font-medium uppercase text-danger">
                                speculative
                              </span>
                            ) : null}
                            <p className="font-medium text-fg">{label || "Theme"}</p>
                            {pos ? <p className="mt-1 text-muted">{pos}</p> : null}
                            {urls.length > 0 ? (
                              <ul className="mt-2 space-y-1 font-mono text-[11px] text-link">
                                {urls.slice(0, 8).map((u) => (
                                  <li key={u}>
                                    <a href={u} target="_blank" rel="noreferrer" className="hover:underline">
                                      {u}
                                    </a>
                                  </li>
                                ))}
                              </ul>
                            ) : null}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
