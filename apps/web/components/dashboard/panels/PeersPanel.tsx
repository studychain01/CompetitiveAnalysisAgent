import type { RunSyncResponse } from "@/lib/types";

type Props = {
  run: RunSyncResponse;
};

export function PeersPanel({ run }: Props) {
  const digests = run.peer_research_digests || {};
  const overall = typeof digests.status === "string" ? digests.status : "";
  const reason = typeof digests.reason === "string" ? digests.reason : "";
  const byPeer =
    digests.by_peer && typeof digests.by_peer === "object"
      ? (digests.by_peer as Record<string, Record<string, unknown>>)
      : {};

  const keys = Object.keys(byPeer);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="rounded-lg border border-border bg-surface-elevated px-4 py-3 text-sm">
        <p className="text-fg">
          Peer batch: <span className="font-mono text-muted">{overall || "—"}</span>
        </p>
        {reason ? <p className="mt-2 text-muted">{reason}</p> : null}
      </div>

      {keys.length === 0 ? (
        <p className="text-sm text-muted">No per-peer digest rows.</p>
      ) : (
        <div className="space-y-4">
          {keys.map((key) => {
            const row = byPeer[key] || {};
            const displayName = typeof row.display_name === "string" ? row.display_name : key;
            const rowStatus = typeof row.status === "string" ? row.status : "";
            const digest = row.digest && typeof row.digest === "object" ? (row.digest as Record<string, unknown>) : null;

            return (
              <details
                key={key}
                className="group rounded-xl border border-border bg-surface-elevated open:bg-surface"
              >
                <summary className="cursor-pointer list-none px-4 py-3 [&::-webkit-details-marker]:hidden">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-fg">{displayName}</span>
                    <span
                      className={
                        rowStatus === "ok"
                          ? "rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success"
                          : "rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning"
                      }
                    >
                      {rowStatus || "unknown"}
                    </span>
                  </div>
                </summary>
                <div className="border-t border-border px-4 py-3">
                  {digest ? (
                    <pre className="max-h-[420px] overflow-auto font-mono text-[11px] leading-relaxed text-muted">
                      {JSON.stringify(digest, null, 2)}
                    </pre>
                  ) : (
                    <p className="text-sm text-muted">No digest object.</p>
                  )}
                </div>
              </details>
            );
          })}
        </div>
      )}
    </div>
  );
}
