"use client";

import { useEffect, useMemo, useState } from "react";

import type { RunSyncResponse } from "@/lib/types";

type Props = {
  run: RunSyncResponse;
};

const LIST_CAP = 6;

const PEER_LEFT_ACCENT = [
  "border-l-[3px] border-l-accent/45",
  "border-l-[3px] border-l-success/45",
  "border-l-[3px] border-l-link/45",
] as const;

const AXIS_LEFT_ACCENT = ["border-l-[3px] border-l-accent/40", "border-l-[3px] border-l-link/40"] as const;

function asString(v: unknown): string {
  return typeof v === "string" ? v.trim() : "";
}

function asNumber(v: unknown): number | null {
  if (typeof v !== "number" || Number.isNaN(v)) return null;
  return v;
}

function stringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string" && x.trim().length > 0).map((s) => s.trim());
}

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function shortLinkLabel(url: string): string {
  try {
    const u = new URL(url);
    const path = u.pathname === "/" ? "" : u.pathname;
    const tail = path.length > 28 ? `${path.slice(0, 26)}…` : path;
    return `${u.host}${tail}`;
  } catch {
    return url.length > 42 ? `${url.slice(0, 40)}…` : url;
  }
}

function confidenceTextClass(conf: number): string {
  const c = Math.min(1, Math.max(0, conf));
  if (c >= 0.75) return "text-success";
  if (c >= 0.45) return "text-warning";
  return "text-muted";
}

function confidencePillClass(conf: number): string {
  const c = Math.min(1, Math.max(0, conf));
  if (c >= 0.75) return "bg-success/15 text-success";
  if (c >= 0.45) return "bg-warning/15 text-warning";
  return "bg-surface-elevated text-muted";
}

function AheadAxesSection({ axes }: { axes: unknown[] }) {
  const filtered = axes
    .map((raw) => asRecord(raw))
    .filter((ax): ax is Record<string, unknown> => {
      if (!ax) return false;
      return Boolean(asString(ax.axis) || asString(ax.rationale));
    });
  if (!filtered.length) return null;
  return (
    <section className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-subtle">Where they lead</h3>
      <div className="space-y-3">
        {filtered.map((ax, i) => {
          const axis = asString(ax.axis);
          const rationale = asString(ax.rationale);
          const urls = Array.isArray(ax.source_urls) ? (ax.source_urls as string[]) : [];
          const conf = asNumber(ax.confidence);
          const bar = AXIS_LEFT_ACCENT[i % AXIS_LEFT_ACCENT.length];
          return (
            <div
              key={`${axis}-${i}`}
              className={`rounded-xl border border-border bg-surface-elevated/50 py-3 pl-4 pr-4 shadow-sm ${bar}`}
            >
              {axis ? <p className="text-sm font-semibold tracking-tight text-fg">{axis}</p> : null}
              {rationale ? <p className="mt-2 text-sm leading-relaxed text-muted">{rationale}</p> : null}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {conf !== null ? (
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold tabular-nums ${confidencePillClass(conf)}`}
                  >
                    {Math.round(conf * 100)}% confidence
                  </span>
                ) : null}
              </div>
              {urls.length > 0 ? (
                <ul className="mt-3 space-y-1.5 border-t border-border pt-3">
                  {urls.slice(0, 8).map((u) => (
                    <li key={u}>
                      <a
                        href={u}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-mono text-[11px] text-link hover:underline"
                      >
                        <span className="truncate">{shortLinkLabel(u)}</span>
                        <span aria-hidden>↗</span>
                      </a>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function PowerUsersSection({ pu }: { pu: Record<string, unknown> }) {
  const segment = asString(pu.segment_label);
  const jobs = stringArray(pu.jobs_to_be_done);
  const signals = stringArray(pu.signals);
  if (!segment && !jobs.length && !signals.length) return null;

  const showJobs = jobs.slice(0, LIST_CAP);
  const restJobs = jobs.length - showJobs.length;
  const showSig = signals.slice(0, LIST_CAP);
  const restSig = signals.length - showSig.length;

  return (
    <section className="rounded-xl border border-border border-l-[3px] border-l-accent/35 bg-accent-subtle/30 px-4 py-4 shadow-sm">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-accent">Power users</h3>
      {segment ? <p className="mt-2 text-sm font-medium leading-relaxed text-fg">{segment}</p> : null}
      {showJobs.length > 0 ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-subtle">Jobs to be done</p>
          <ul className="mt-1.5 list-inside list-disc space-y-1 text-sm leading-relaxed text-muted">
            {showJobs.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
          {restJobs > 0 ? <p className="mt-1 text-xs text-muted">+{restJobs} more</p> : null}
        </div>
      ) : null}
      {showSig.length > 0 ? (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-subtle">Signals</p>
          <ul className="mt-1.5 list-inside list-disc space-y-1 text-sm leading-relaxed text-muted">
            {showSig.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
          {restSig > 0 ? <p className="mt-1 text-xs text-muted">+{restSig} more</p> : null}
        </div>
      ) : null}
    </section>
  );
}

function PeerDigestContent({ digest }: { digest: Record<string, unknown> }) {
  const axesRaw = Array.isArray(digest.ahead_axes) ? digest.ahead_axes : [];
  const pu = asRecord(digest.power_user_hypothesis);
  const evidenceNotes = asString(digest.evidence_notes);
  const peerEcho = asString(digest.peer_display_name);

  return (
    <div className="space-y-6 pt-1">
      {peerEcho ? <p className="text-xs text-muted">Digest target: {peerEcho}</p> : null}
      <AheadAxesSection axes={axesRaw} />
      {pu ? <PowerUsersSection pu={pu} /> : null}
      {evidenceNotes ? (
        <div className="rounded-lg border-l-4 border-l-warning/45 bg-warning/8 px-4 py-3 text-sm leading-relaxed text-fg">
          <p className="text-xs font-semibold uppercase tracking-wide text-warning">Evidence notes</p>
          <p className="mt-2 text-muted">{evidenceNotes}</p>
        </div>
      ) : null}
    </div>
  );
}

type PeerEntry = { key: string; row: Record<string, unknown>; displayName: string };

/** Stable fallback so `useMemo` / effects do not see a new object every render. */
const EMPTY_BY_PEER: Record<string, Record<string, unknown>> = {};

export function PeersPanel({ run }: Props) {
  const digests = run.peer_research_digests;
  const overall = digests && typeof digests.status === "string" ? digests.status : "";
  const reason = digests && typeof digests.reason === "string" ? digests.reason : "";
  const byPeer =
    digests?.by_peer && typeof digests.by_peer === "object"
      ? (digests.by_peer as Record<string, Record<string, unknown>>)
      : EMPTY_BY_PEER;

  const entries = useMemo(() => {
    const list: PeerEntry[] = Object.keys(byPeer).map((key) => {
      const row = byPeer[key] || {};
      const displayName = typeof row.display_name === "string" ? row.display_name.trim() || key : key;
      return { key, row, displayName };
    });
    list.sort((a, b) => a.displayName.localeCompare(b.displayName, undefined, { sensitivity: "base" }));
    return list;
  }, [byPeer]);

  const peerFingerprint = entries.map((e) => e.key).join("|");
  const [openPeerKeys, setOpenPeerKeys] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    if (!peerFingerprint) {
      setOpenPeerKeys(new Set());
      return;
    }
    const firstKey = peerFingerprint.split("|")[0] ?? "";
    setOpenPeerKeys(new Set(firstKey ? [firstKey] : []));
  }, [peerFingerprint]);

  const batchPill =
    overall === "ok"
      ? "bg-success/15 text-success"
      : overall === "partial"
        ? "bg-warning/15 text-warning"
        : overall
          ? "bg-danger/10 text-danger"
          : "bg-surface-elevated text-muted";

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="rounded-2xl border border-border border-l-[3px] border-l-accent/40 bg-surface px-5 py-4 text-sm shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold text-fg">Deep dives</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              Parallel research on up to <span className="font-medium text-fg">three</span> rivals—the
              highest-confidence names from your Competitors shortlist—so each run stays bounded and
              evidence-heavy. Axes, sources, and power-user hypotheses below; the full landscape stays on{" "}
              <span className="font-medium text-fg">Competitors</span>.
            </p>
          </div>
          <span className={`rounded-full px-3 py-0.5 text-xs font-semibold capitalize ${batchPill}`}>
            {overall || "—"}
          </span>
        </div>
        {reason ? <p className="mt-3 w-full border-t border-border pt-3 text-muted">{reason}</p> : null}
      </div>

      {entries.length === 0 ? (
        <p className="text-sm text-muted">No per-peer digest rows.</p>
      ) : (
        <div className="space-y-5">
          {entries.map(({ key, row, displayName }, peerIdx) => {
            const rowStatus = typeof row.status === "string" ? row.status : "";
            const digest = row.digest && typeof row.digest === "object" ? (row.digest as Record<string, unknown>) : null;
            const overallConf = digest ? asNumber(digest.overall_confidence) : null;
            const peerBar = PEER_LEFT_ACCENT[peerIdx % PEER_LEFT_ACCENT.length];

            return (
              <details
                key={key}
                open={openPeerKeys.has(key)}
                onToggle={(e) => {
                  const el = e.currentTarget;
                  const next = el.open;
                  setOpenPeerKeys((prev) => {
                    const s = new Set(prev);
                    if (next) s.add(key);
                    else s.delete(key);
                    return s;
                  });
                }}
                className={`group rounded-2xl border border-border bg-surface shadow-sm ${peerBar}`}
              >
                <summary className="cursor-pointer list-none px-5 py-4 [&::-webkit-details-marker]:hidden">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <span className="text-lg font-semibold tracking-tight text-fg">{displayName}</span>
                      {overallConf !== null ? (
                        <p className={`mt-1 text-xs font-medium tabular-nums ${confidenceTextClass(overallConf)}`}>
                          Digest confidence {Math.round(overallConf * 100)}%
                        </p>
                      ) : null}
                    </div>
                    <span
                      className={
                        rowStatus === "ok"
                          ? "shrink-0 rounded-full bg-success/15 px-2.5 py-0.5 text-xs font-semibold capitalize text-success"
                          : "shrink-0 rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-semibold capitalize text-warning"
                      }
                    >
                      {rowStatus || "unknown"}
                    </span>
                  </div>
                  <span className="mt-2 inline-block text-xs font-medium text-accent group-open:hidden">
                    Expand peer digest
                  </span>
                  <span className="mt-2 hidden text-xs font-medium text-accent group-open:inline">Collapse</span>
                </summary>
                <div className="border-t border-border px-5 py-5">
                  {digest ? (
                    <>
                      <PeerDigestContent digest={digest} />
                      <details className="mt-6 rounded-lg border border-dashed border-border bg-surface-elevated/40 px-3 py-2">
                        <summary className="cursor-pointer text-xs font-medium text-subtle">Raw JSON</summary>
                        <pre className="mt-2 max-h-[280px] overflow-auto font-mono text-[10px] leading-relaxed text-muted">
                          {JSON.stringify(digest, null, 2)}
                        </pre>
                      </details>
                    </>
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
