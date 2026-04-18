import type { RunSyncResponse } from "@/lib/types";

type Props = {
  run: RunSyncResponse;
};

export function RiskPanel({ run }: Props) {
  const d = run.sec_risk_dossier || {};
  const status = typeof d.status === "string" ? d.status : "unknown";
  const reason = typeof d.reason === "string" ? d.reason : "";
  const bullets = Array.isArray(d.risk_theme_bullets) ? (d.risk_theme_bullets as unknown[]) : [];

  const isError = status === "error" || status === "skipped";
  const isPartial = status === "partial";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div
        className={`rounded-lg border px-4 py-3 text-sm ${
          isError
            ? "border-danger/50 bg-danger/10"
            : isPartial
              ? "border-warning/50 bg-warning/10"
              : "border-border bg-surface-elevated"
        }`}
      >
        <p className="font-medium text-fg">
          Status: <span className="font-mono text-muted">{status}</span>
        </p>
        {reason ? <p className="mt-2 text-muted">{reason}</p> : null}
      </div>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-subtle">10-K risk themes</h2>
        {bullets.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No risk theme bullets in this dossier.</p>
        ) : (
          <ul className="mt-3 list-inside list-decimal space-y-2 text-sm leading-relaxed text-fg">
            {bullets.map((b, i) => (
              <li key={i} className="pl-1">
                {String(b)}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
