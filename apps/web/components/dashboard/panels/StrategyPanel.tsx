import type { RunSyncResponse } from "@/lib/types";

type Props = {
  run: RunSyncResponse;
};

export function StrategyPanel({ run }: Props) {
  const s = run.competitive_strategy || {};
  const matrix = Array.isArray(s.advantage_gap_matrix)
    ? (s.advantage_gap_matrix as Record<string, unknown>[])
    : [];
  const moves = Array.isArray(s.prioritized_moves) ? (s.prioritized_moves as Record<string, unknown>[]) : [];
  const shortPlan = s.short_term_plan && typeof s.short_term_plan === "object" ? (s.short_term_plan as Record<string, unknown>) : null;
  const longPlan = s.long_term_plan && typeof s.long_term_plan === "object" ? (s.long_term_plan as Record<string, unknown>) : null;
  const nonGoals = Array.isArray(s.non_goals) ? (s.non_goals as string[]) : [];
  const lowFruit = Array.isArray(s.low_hanging_fruits) ? (s.low_hanging_fruits as string[]) : [];
  const longTargets = Array.isArray(s.long_term_targets) ? (s.long_term_targets as string[]) : [];
  const iq = s.input_quality && typeof s.input_quality === "object" ? (s.input_quality as Record<string, unknown>) : null;

  const degraded =
    iq && (Boolean(iq.competitor_landscape_degraded) || Number(iq.competitor_count) < 3);

  return (
    <div className="mx-auto max-w-5xl space-y-10">
      {degraded ? (
        <div className="rounded-lg border-l-4 border-warning bg-warning/10 px-4 py-3 text-sm text-fg">
          <p className="font-medium text-warning">Strategy may be directional only</p>
          {typeof iq?.notes === "string" && iq.notes ? <p className="mt-1 text-muted">{iq.notes}</p> : null}
        </div>
      ) : null}

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-subtle">Advantage / gap matrix</h2>
        {matrix.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No matrix rows.</p>
        ) : (
          <div className="mt-3 overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[640px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-elevated text-xs uppercase tracking-wide text-subtle">
                  <th className="p-3 font-medium">Peer</th>
                  <th className="p-3 font-medium">Axis / advantage</th>
                  <th className="p-3 font-medium">Peer evidence</th>
                  <th className="p-3 font-medium">Home gap</th>
                  <th className="p-3 font-medium">URLs</th>
                </tr>
              </thead>
              <tbody>
                {matrix.map((row, i) => (
                  <tr key={i} className="border-b border-border last:border-0 hover:bg-surface-elevated/50">
                    <td className="p-3 align-top text-fg">{String(row.peer_name ?? "")}</td>
                    <td className="p-3 align-top text-muted">{String(row.axis_or_advantage ?? "")}</td>
                    <td className="p-3 align-top text-muted">{String(row.peer_evidence_summary ?? "")}</td>
                    <td className="p-3 align-top text-fg">{String(row.home_gap ?? "")}</td>
                    <td className="p-3 align-top font-mono text-[11px] text-link">
                      {Array.isArray(row.source_urls)
                        ? (row.source_urls as string[]).slice(0, 5).map((u) => (
                            <div key={u}>
                              <a href={u} target="_blank" rel="noreferrer" className="break-all hover:underline">
                                {u}
                              </a>
                            </div>
                          ))
                        : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-subtle">Prioritized moves</h2>
        {moves.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No moves.</p>
        ) : (
          <div className="mt-3 overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[560px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-elevated text-xs uppercase tracking-wide text-subtle">
                  <th className="p-3 font-medium">#</th>
                  <th className="p-3 font-medium">Title</th>
                  <th className="p-3 font-medium">Horizon</th>
                  <th className="p-3 font-medium">Effort</th>
                  <th className="p-3 font-medium">Risk to home</th>
                </tr>
              </thead>
              <tbody>
                {moves.map((row, i) => (
                  <tr key={i} className="border-b border-border last:border-0 hover:bg-surface-elevated/50">
                    <td className="p-3 font-mono text-muted">{String(row.rank ?? i + 1)}</td>
                    <td className="p-3 text-fg">
                      <div className="font-medium">{String(row.title ?? "")}</div>
                      {row.rationale ? (
                        <div className="mt-1 text-xs text-muted">{String(row.rationale)}</div>
                      ) : null}
                    </td>
                    <td className="p-3 text-muted">{String(row.horizon ?? "")}</td>
                    <td className="p-3 text-muted">{String(row.effort ?? "")}</td>
                    <td className="p-3 text-danger/90">{String(row.risk_to_home ?? "")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-xl border border-border bg-surface-elevated p-4">
          <h2 className="text-sm font-semibold text-subtle">
            {typeof shortPlan?.horizon_label === "string" ? shortPlan.horizon_label : "Short term"}
          </h2>
          <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-fg">
            {Array.isArray(shortPlan?.bullets) && (shortPlan.bullets as string[]).length ? (
              (shortPlan.bullets as string[]).map((b, i) => <li key={i}>{b}</li>)
            ) : (
              <li className="text-muted">No bullets.</li>
            )}
          </ul>
        </section>
        <section className="rounded-xl border border-border bg-surface-elevated p-4">
          <h2 className="text-sm font-semibold text-subtle">
            {typeof longPlan?.horizon_label === "string" ? longPlan.horizon_label : "Long term"}
          </h2>
          <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-fg">
            {Array.isArray(longPlan?.bullets) && (longPlan.bullets as string[]).length ? (
              (longPlan.bullets as string[]).map((b, i) => <li key={i}>{b}</li>)
            ) : (
              <li className="text-muted">No bullets.</li>
            )}
          </ul>
        </section>
      </div>

      <section className="flex flex-wrap gap-2">
        <h2 className="w-full text-sm font-semibold uppercase tracking-wide text-subtle">Non-goals</h2>
        {nonGoals.length === 0 ? (
          <p className="text-sm text-muted">None listed.</p>
        ) : (
          nonGoals.map((t) => (
            <span key={t} className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted">
              {t}
            </span>
          ))
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-subtle">Low-hanging fruit</h2>
          <ul className="mt-2 list-inside list-disc text-sm text-fg">
            {lowFruit.length ? lowFruit.map((t, i) => <li key={i}>{t}</li>) : <li className="text-muted">—</li>}
          </ul>
        </div>
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-subtle">Long-term targets</h2>
          <ul className="mt-2 list-inside list-disc text-sm text-fg">
            {longTargets.length ? (
              longTargets.map((t, i) => <li key={i}>{t}</li>)
            ) : (
              <li className="text-muted">—</li>
            )}
          </ul>
        </div>
      </section>
    </div>
  );
}
