import type { RunSyncResponse } from "@/lib/types";

type Props = {
  run: RunSyncResponse;
};

function getInputQuality(strategy: Record<string, unknown>) {
  const iq = strategy.input_quality;
  if (!iq || typeof iq !== "object") return null;
  return iq as Record<string, unknown>;
}

export function OverviewPanel({ run }: Props) {
  const profile = run.company_profile || {};
  const strategy = run.competitive_strategy || {};
  const summary =
    (typeof strategy.executive_summary === "string" && strategy.executive_summary) ||
    (typeof profile.summary === "string" && profile.summary) ||
    "";

  const iq = getInputQuality(strategy);
  const degraded =
    iq && (Boolean(iq.competitor_landscape_degraded) || Number(iq.competitor_count) < 3);
  const iqNotes = typeof iq?.notes === "string" ? iq.notes : "";

  const stratStatus = typeof strategy.status === "string" ? strategy.status : "";
  const stratReason = typeof strategy.reason === "string" ? strategy.reason : "";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {degraded ? (
        <div
          className="rounded-lg border-l-4 border-warning bg-warning/10 px-4 py-3 text-sm text-fg"
          role="status"
        >
          <p className="font-medium text-warning">Partial or degraded inputs</p>
          {iqNotes ? <p className="mt-1 text-muted">{iqNotes}</p> : null}
        </div>
      ) : null}

      {stratStatus && stratStatus !== "ok" ? (
        <div
          className={`rounded-lg border-l-4 px-4 py-3 text-sm ${
            stratStatus === "error"
              ? "border-danger bg-danger/10 text-fg"
              : stratStatus === "skipped"
                ? "border-border bg-surface-elevated text-muted"
                : "border-warning bg-warning/10 text-fg"
          }`}
          role="status"
        >
          <p className="font-medium">
            Strategy: <span className="font-mono">{stratStatus}</span>
          </p>
          {stratReason ? <p className="mt-1 text-muted">{stratReason}</p> : null}
        </div>
      ) : null}

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-subtle">Company</h2>
        <dl className="mt-3 space-y-2 text-sm">
          {typeof profile.name === "string" && profile.name ? (
            <div>
              <dt className="text-muted">Name</dt>
              <dd className="text-fg">{profile.name}</dd>
            </div>
          ) : null}
          {typeof profile.category === "string" && profile.category ? (
            <div>
              <dt className="text-muted">Category</dt>
              <dd className="text-fg">{profile.category}</dd>
            </div>
          ) : null}
          {typeof profile.business_model === "string" && profile.business_model ? (
            <div>
              <dt className="text-muted">Business model</dt>
              <dd className="text-fg">{profile.business_model}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-subtle">Executive summary</h2>
        {summary ? (
          <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-fg">{summary}</p>
        ) : (
          <p className="mt-3 text-sm text-muted">No summary returned for this run.</p>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-subtle">Run</h2>
        <p className="mt-2 font-mono text-xs text-muted">
          stage: <span className="text-fg">{run.stage}</span>
        </p>
      </section>
    </div>
  );
}
