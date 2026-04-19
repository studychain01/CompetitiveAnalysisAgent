"use client";

import { useState } from "react";

import type { RunSyncResponse } from "@/lib/types";

type Props = {
  run: RunSyncResponse;
};

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

function formatHorizonLabel(raw: string): string {
  const low = (raw || "").toLowerCase().trim();
  if (!low) return "—";
  if (low.includes("short") || low.includes("0–90") || low.includes("0-90") || low === "short") return "0–90 days";
  if (low.includes("long") || low.includes("6–24") || low.includes("6-24") || low.includes("24m"))
    return "6–24 months";
  return raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatEffortLabel(raw: string): string {
  const low = (raw || "").toLowerCase().trim();
  if (!low) return "—";
  if (low.includes("low") && low.includes("hang")) return "Quick win";
  if (low === "medium" || low.includes("medium")) return "Medium effort";
  if (low.includes("heavy")) return "Heavy lift";
  return raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function evidenceTierPill(tier: string) {
  const t = (tier || "mixed").toLowerCase();
  if (t === "strong") {
    return (
      <span className="shrink-0 rounded-full border border-emerald-700/25 bg-emerald-600 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white shadow-sm">
        Strong signal
      </span>
    );
  }
  if (t === "thin") {
    return (
      <span className="shrink-0 rounded-full border border-amber-800/30 bg-amber-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-amber-950 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-100">
        Thin evidence
      </span>
    );
  }
  return (
    <span className="shrink-0 rounded-full border border-border bg-surface-elevated px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-fg ring-1 ring-border/60">
      Mixed
    </span>
  );
}

function CrossPeerLeverCard({ row }: { row: Record<string, unknown> }) {
  const headline = String(row.headline ?? "").trim();
  const pattern = String(row.pattern ?? "").trim();
  const homeGap = String(row.home_gap ?? "").trim();
  const move = String(row.move ?? "").trim();
  const tier = String(row.evidence_tier ?? "mixed");

  const line = (s: string) =>
    s ? (
      <p className="max-w-prose text-pretty text-fg">{s}</p>
    ) : (
      <p className="text-sm text-muted">—</p>
    );

  return (
    <article className="rounded-xl border border-border/80 bg-surface px-4 py-4 shadow-sm ring-1 ring-border/30 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="min-w-0 flex-1 text-base font-semibold leading-snug tracking-tight text-fg">
          {headline || "Theme"}
        </h3>
        {evidenceTierPill(tier)}
      </div>
      <dl className="mt-4 space-y-3 text-sm leading-relaxed">
        <div className="rounded-lg border border-link/15 border-l-4 border-l-link bg-link/[0.05] px-3 py-2.5">
          <dt className="text-[10px] font-bold uppercase tracking-wide text-link">Rival pattern</dt>
          <dd className="mt-1">{line(pattern)}</dd>
        </div>
        <div className="rounded-lg border border-warning/20 border-l-4 border-l-warning bg-warning/[0.06] px-3 py-2.5">
          <dt className="text-[10px] font-bold uppercase tracking-wide text-warning">Your gap</dt>
          <dd className="mt-1">{line(homeGap)}</dd>
        </div>
        <div className="rounded-lg border border-accent/12 border-l-4 border-l-accent bg-accent-subtle/20 px-3 py-2.5">
          <dt className="text-[10px] font-bold uppercase tracking-wide text-accent">Focus</dt>
          <dd className="mt-1">{line(move)}</dd>
        </div>
      </dl>
    </article>
  );
}

const MATRIX_BAR = ["border-l-accent/50", "border-l-link/50"] as const;

function normPeerLabel(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, " ");
}

/** Split long stance text into paragraphs for easier scanning. */
function proseParagraphs(text: string): string[] {
  const t = text.trim();
  if (!t) return [];
  const chunks = t.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);
  return chunks.length ? chunks : [t];
}

function matrixRowsForPeer(matrix: Record<string, unknown>[], peerName: string): Record<string, unknown>[] {
  const n = normPeerLabel(peerName);
  if (!n) return [];
  return matrix.filter((r) => normPeerLabel(String(r.peer_name ?? "")) === n);
}

/** Section callout: chip + title + body — consistent “deck” rhythm for the tab. */
function StrategySectionIntro({
  chip,
  title,
  description,
  accent = "indigo",
}: {
  chip: string;
  title: string;
  description: string;
  accent?: "indigo" | "slate" | "violet";
}) {
  const shell =
    accent === "slate"
      ? "border-l-slate-400/60 bg-gradient-to-br from-surface to-surface-elevated/60"
      : accent === "violet"
        ? "border-l-link/45 bg-gradient-to-br from-link/[0.06] to-surface"
        : "border-l-accent/50 bg-gradient-to-br from-accent/[0.07] to-surface";

  const chipCls =
    accent === "slate"
      ? "bg-surface-elevated text-muted ring-1 ring-border"
      : accent === "violet"
        ? "bg-accent-subtle text-link ring-1 ring-link/25"
        : "bg-accent-subtle text-accent ring-1 ring-accent/30";

  return (
    <div
      className={`rounded-2xl border border-border border-l-[3px] px-5 py-4 shadow-sm ${shell}`}
    >
      <div className="flex flex-wrap items-start gap-3">
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${chipCls}`}
        >
          {chip}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold tracking-tight text-fg">{title}</h2>
          <p className="mt-1.5 text-sm leading-relaxed text-muted">{description}</p>
        </div>
      </div>
    </div>
  );
}

function MatrixInsightCard({
  row,
  index,
  nested,
}: {
  row: Record<string, unknown>;
  index: number;
  nested?: boolean;
}) {
  const peer = String(row.peer_name ?? "").trim();
  const axis = String(row.axis_or_advantage ?? "").trim();
  const evidence = String(row.peer_evidence_summary ?? "").trim();
  const gap = String(row.home_gap ?? "").trim();
  const urls = Array.isArray(row.source_urls) ? (row.source_urls as string[]) : [];
  const bar = MATRIX_BAR[index % MATRIX_BAR.length];

  return (
    <article
      className={`rounded-xl border border-border border-l-[3px] bg-surface p-4 shadow-sm ring-1 ring-border/30 ${bar}`}
    >
      <header className="border-b border-border/60 pb-2.5">
        {nested ? (
          <p className="text-[10px] font-bold uppercase tracking-wider text-subtle">Axis detail</p>
        ) : (
          <p className="text-[10px] font-bold uppercase tracking-wider text-subtle">
            {peer ? <>vs {peer}</> : <>Competitive row</>}
          </p>
        )}
        {axis ? <p className="mt-1 text-sm font-semibold leading-snug text-fg">{axis}</p> : null}
      </header>
      <div className="mt-4 grid gap-4 lg:grid-cols-2 lg:gap-5">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-muted">Situation</p>
          <p className="mt-1.5 max-w-prose text-pretty text-sm leading-relaxed text-fg">{evidence || "—"}</p>
        </div>
        <div className="rounded-lg border border-accent/15 bg-accent-subtle/25 px-3 py-3 lg:px-4">
          <p className="text-[10px] font-bold uppercase tracking-wide text-accent">Implication for your company</p>
          <p className="mt-1.5 max-w-prose text-pretty text-sm leading-relaxed text-fg">{gap || "—"}</p>
        </div>
      </div>
      {urls.length > 0 ? (
        <details className="mt-5 rounded-xl border border-dashed border-border bg-surface-elevated/40 px-3 py-2">
          <summary className="cursor-pointer text-xs font-medium text-subtle">Sources ({urls.length})</summary>
          <ul className="mt-3 space-y-2">
            {urls.map((u) => (
              <li key={u}>
                <a
                  href={u}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-[11px] text-link hover:underline"
                >
                  <span className="break-all">{shortLinkLabel(u)}</span>
                  <span aria-hidden>↗</span>
                </a>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </article>
  );
}

function PrioritizedMoveCard({ row, index }: { row: Record<string, unknown>; index: number }) {
  const [expanded, setExpanded] = useState(index === 0);
  const rank = String(row.rank ?? index + 1);
  const title = String(row.title ?? "").trim();
  const rationale = row.rationale ? String(row.rationale).trim() : "";
  const horizon = String(row.horizon ?? "");
  const effort = String(row.effort ?? "");
  const risk = String(row.risk_to_home ?? "").trim();
  const hasBody = Boolean(rationale || risk);

  return (
    <div className="border-b border-border/60 py-4 last:border-0 last:pb-0 first:pt-0">
      <div className="flex gap-4">
        <div
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent-subtle text-sm font-bold tabular-nums text-accent ring-1 ring-accent/20"
          aria-hidden
        >
          {rank}
        </div>
        <div className="min-w-0 flex-1">
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={hasBody ? `${expanded ? "Collapse" : "Expand"} details for move: ${title || "Move"}` : undefined}
            onClick={() => {
              if (!hasBody) return;
              setExpanded((e) => !e);
            }}
            className={`w-full rounded-xl text-left transition ${
              hasBody
                ? "cursor-pointer hover:bg-surface-elevated/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                : "cursor-default"
            }`}
          >
            <div className="flex items-start justify-between gap-3 px-1 py-0.5">
              <h3 className="min-w-0 flex-1 pr-2 text-[17px] font-semibold leading-snug tracking-tight text-fg">
                {title || "Move"}
              </h3>
              {hasBody ? (
                <span className="mt-0.5 shrink-0 text-muted" aria-hidden>
                  <span
                    className={`inline-block text-xs transition-transform ${expanded ? "rotate-0" : "-rotate-90"}`}
                  >
                    ▼
                  </span>
                </span>
              ) : null}
            </div>
            {!hasBody ? (
              <p className="mt-2 px-1 text-xs text-subtle">No rationale or risk detail to expand.</p>
            ) : null}
          </button>
          {expanded && hasBody ? (
            <div className="mt-3 border-t border-border/50 pt-3 pl-1">
              {horizon || effort ? (
                <p className="mb-2 text-xs leading-relaxed text-subtle">
                  {horizon ? (
                    <>
                      <span className="font-semibold text-muted">Time horizon:</span> {formatHorizonLabel(horizon)}
                    </>
                  ) : null}
                  {horizon && effort ? <span className="text-subtle"> · </span> : null}
                  {effort ? (
                    <>
                      <span className="font-semibold text-muted">Effort:</span> {formatEffortLabel(effort)}
                    </>
                  ) : null}
                </p>
              ) : null}
              {rationale ? (
                <p className="max-w-prose text-pretty text-[15px] leading-relaxed text-muted">{rationale}</p>
              ) : null}
              {risk ? (
                <div
                  className={`rounded-lg border border-danger/15 bg-danger/[0.04] px-3 py-2.5 ${rationale ? "mt-3" : ""}`}
                >
                  <p className="text-[10px] font-bold uppercase tracking-wide text-danger">Risk to your company</p>
                  <p className="mt-1.5 max-w-prose text-pretty text-sm leading-relaxed text-danger/95">{risk}</p>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function PeerDeepDiveCard({
  row,
  index,
  total,
  matrixRows,
}: {
  row: Record<string, unknown>;
  index: number;
  total: number;
  matrixRows: Record<string, unknown>[];
}) {
  const [expanded, setExpanded] = useState(index === 0);
  const peer = String(row.peer_name ?? "").trim();
  const stand = String(row.where_home_stands ?? "").trim();
  const shortB = Array.isArray(row.short_term_reconciliation)
    ? (row.short_term_reconciliation as string[]).filter((t) => String(t).trim())
    : [];
  const longB = Array.isArray(row.long_term_reconciliation)
    ? (row.long_term_reconciliation as string[]).filter((t) => String(t).trim())
    : [];
  const watch = String(row.watchouts ?? "").trim();
  const urls = Array.isArray(row.source_urls) ? (row.source_urls as string[]) : [];
  const bar = MATRIX_BAR[index % MATRIX_BAR.length];
  const n = index + 1;

  return (
    <article
      className={`overflow-hidden rounded-2xl border border-border border-l-[4px] bg-surface shadow-lg shadow-slate-900/[0.06] ring-1 ring-border/50 ${bar}`}
    >
      <button
        type="button"
        aria-expanded={expanded}
        aria-label={expanded ? `Collapse ${peer || "competitor"} details` : `Expand ${peer || "competitor"} details`}
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full flex-wrap items-start justify-between gap-3 border-b border-border/80 bg-gradient-to-r from-surface-elevated/50 to-transparent px-5 py-4 text-left transition hover:bg-surface-elevated/80"
      >
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <span
            className={`mt-1.5 shrink-0 text-sm text-subtle transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
            aria-hidden
          >
            ▶
          </span>
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wider text-subtle">Deep dive</p>
            <h3 className="mt-0.5 text-xl font-bold tracking-tight text-fg">{peer || "Competitor"}</h3>
            {!expanded && stand ? (
              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">{stand}</p>
            ) : null}
          </div>
        </div>
        <span className="rounded-full border border-border bg-surface px-3 py-1 font-mono text-xs font-semibold text-muted tabular-nums">
          {n} / {total}
        </span>
      </button>

      {expanded ? (
      <div className="space-y-8 px-5 py-6">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-muted">Your position vs this rival</p>
          <div className="mt-3 max-w-prose space-y-3 text-pretty text-[15px] leading-[1.65] text-fg">
            {stand
              ? proseParagraphs(stand).map((para, i) => <p key={i}>{para}</p>)
              : "—"}
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-2 lg:gap-6">
          <div className="rounded-xl border border-accent/12 bg-accent-subtle/20 p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-accent">Short term · 0–90d</p>
            {shortB.length ? (
              <ul className="mt-3 list-outside list-disc space-y-2.5 pl-4 text-sm leading-snug text-fg marker:text-accent">
                {shortB.map((b, i) => (
                  <li key={i} className="pl-1">
                    {b}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted">—</p>
            )}
          </div>
          <div className="rounded-xl border border-link/12 bg-canvas/80 p-4 ring-1 ring-link/8">
            <p className="text-[10px] font-bold uppercase tracking-wide text-link">Long term · 6–24m</p>
            {longB.length ? (
              <ul className="mt-3 list-outside list-disc space-y-2.5 pl-4 text-sm leading-snug text-fg marker:text-link">
                {longB.map((b, i) => (
                  <li key={i} className="pl-1">
                    {b}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted">—</p>
            )}
          </div>
        </div>

        {watch ? (
          <details className="rounded-xl border border-warning/25 bg-warning/[0.06] px-4 py-3 open:bg-warning/[0.08]">
            <summary className="cursor-pointer list-none text-xs font-bold uppercase tracking-wide text-warning marker:content-none [&::-webkit-details-marker]:hidden">
              Watchouts
            </summary>
            <p className="mt-2 max-w-prose text-pretty text-sm leading-relaxed text-muted">{watch}</p>
          </details>
        ) : null}

        {matrixRows.length > 0 ? (
          <details className="group rounded-xl border border-border/70 bg-surface-elevated/25">
            <summary className="cursor-pointer list-none px-4 py-3.5 text-sm font-medium text-fg marker:content-none [&::-webkit-details-marker]:hidden">
              Supporting axes
              <span className="ml-1.5 font-normal text-muted">({matrixRows.length})</span>
              <span className="ml-2 text-xs font-normal text-subtle group-open:hidden">· optional detail</span>
            </summary>
            <div className="space-y-3 border-t border-border/50 px-4 pb-4 pt-4">
              {matrixRows.map((r, i) => (
                <MatrixInsightCard key={i} row={r} index={i + index} nested />
              ))}
            </div>
          </details>
        ) : null}

        {urls.length > 0 ? (
          <details className="rounded-xl border border-dashed border-border bg-surface-elevated/40 px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-subtle">Sources ({urls.length})</summary>
            <ul className="mt-3 space-y-2">
              {urls.map((u) => (
                <li key={u}>
                  <a
                    href={u}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-[11px] text-link hover:underline"
                  >
                    <span className="break-all">{shortLinkLabel(u)}</span>
                    <span aria-hidden>↗</span>
                  </a>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
      ) : null}
    </article>
  );
}

function CrossPeerHorizons({
  shortPlan,
  longPlan,
}: {
  shortPlan: Record<string, unknown> | null;
  longPlan: Record<string, unknown> | null;
}) {
  const sb =
    shortPlan && Array.isArray(shortPlan.bullets) ? (shortPlan.bullets as string[]).filter((x) => String(x).trim()) : [];
  const lb =
    longPlan && Array.isArray(longPlan.bullets) ? (longPlan.bullets as string[]).filter((x) => String(x).trim()) : [];
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <section className="rounded-2xl border border-border bg-surface p-5 shadow-md shadow-slate-900/[0.04] ring-1 ring-border/40">
        <h2 className="text-sm font-semibold text-accent">
          {shortPlan && typeof shortPlan.horizon_label === "string" ? shortPlan.horizon_label : "Short term (cross-peer)"}
        </h2>
        <ul className="mt-3 list-inside list-disc space-y-2 text-sm leading-relaxed text-fg">
          {sb.length ? sb.map((b, i) => <li key={i}>{b}</li>) : <li className="text-muted">No bullets.</li>}
        </ul>
      </section>
      <section className="rounded-2xl border border-border bg-surface p-5 shadow-md shadow-slate-900/[0.04] ring-1 ring-border/40">
        <h2 className="text-sm font-semibold text-link">
          {longPlan && typeof longPlan.horizon_label === "string" ? longPlan.horizon_label : "Long term (cross-peer)"}
        </h2>
        <ul className="mt-3 list-inside list-disc space-y-2 text-sm leading-relaxed text-fg">
          {lb.length ? lb.map((b, i) => <li key={i}>{b}</li>) : <li className="text-muted">No bullets.</li>}
        </ul>
      </section>
    </div>
  );
}

function FullMatrixTable({ matrix }: { matrix: Record<string, unknown>[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface shadow-sm">
      <table className="w-full min-w-[640px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-elevated text-xs uppercase tracking-wide text-subtle">
            <th className="p-3 font-semibold">Peer</th>
            <th className="p-3 font-semibold">Axis / advantage</th>
            <th className="p-3 font-semibold">Peer evidence</th>
            <th className="p-3 font-semibold">Your gap</th>
            <th className="p-3 font-semibold">Sources</th>
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              <td className="p-3 align-top font-medium text-fg">{String(row.peer_name ?? "")}</td>
              <td className="p-3 align-top text-muted">{String(row.axis_or_advantage ?? "")}</td>
              <td className="p-3 align-top text-muted">{String(row.peer_evidence_summary ?? "")}</td>
              <td className="p-3 align-top text-fg">{String(row.home_gap ?? "")}</td>
              <td className="p-3 align-top">
                {Array.isArray(row.source_urls)
                  ? (row.source_urls as string[]).slice(0, 5).map((u) => (
                      <div key={u} className="mb-1.5 last:mb-0">
                        <a
                          href={u}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 font-mono text-[11px] text-link hover:underline"
                        >
                          <span className="truncate">{shortLinkLabel(u)}</span>
                          <span aria-hidden>↗</span>
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
  );
}

function FullMovesTable({ moves }: { moves: Record<string, unknown>[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface shadow-sm">
      <table className="w-full min-w-[480px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-elevated text-xs uppercase tracking-wide text-subtle">
            <th className="p-3 font-semibold">#</th>
            <th className="p-3 font-semibold">Title</th>
            <th className="p-3 font-semibold">Risk to your company</th>
          </tr>
        </thead>
        <tbody>
          {moves.map((row, i) => {
            const h = String(row.horizon ?? "");
            const e = String(row.effort ?? "");
            const scope =
              h || e
                ? `Time horizon: ${formatHorizonLabel(h)} · Effort: ${formatEffortLabel(e)}`
                : "";
            return (
              <tr key={i} className="border-b border-border last:border-0">
                <td className="p-3 font-mono text-muted">{String(row.rank ?? i + 1)}</td>
                <td className="p-3 text-fg">
                  <div className="font-semibold">{String(row.title ?? "")}</div>
                  {scope ? <div className="mt-1 text-[11px] leading-relaxed text-subtle">{scope}</div> : null}
                  {row.rationale ? (
                    <div className="mt-1 text-xs leading-relaxed text-muted">{String(row.rationale)}</div>
                  ) : null}
                </td>
                <td className="p-3 align-top text-sm text-danger">{String(row.risk_to_home ?? "")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function StrategyPanel({ run }: Props) {
  const s = run.competitive_strategy || {};
  const matrix = Array.isArray(s.advantage_gap_matrix)
    ? (s.advantage_gap_matrix as Record<string, unknown>[])
    : [];
  const moves = Array.isArray(s.prioritized_moves) ? (s.prioritized_moves as Record<string, unknown>[]) : [];
  const peerDeepDives = Array.isArray(s.peer_deep_dives) ? (s.peer_deep_dives as Record<string, unknown>[]) : [];
  const shortPlan = s.short_term_plan && typeof s.short_term_plan === "object" ? (s.short_term_plan as Record<string, unknown>) : null;
  const longPlan = s.long_term_plan && typeof s.long_term_plan === "object" ? (s.long_term_plan as Record<string, unknown>) : null;
  const crossPeerLevers = Array.isArray(s.cross_peer_levers)
    ? (s.cross_peer_levers as Record<string, unknown>[]).filter((r) => r && typeof r === "object")
    : [];
  const iq = s.input_quality && typeof s.input_quality === "object" ? (s.input_quality as Record<string, unknown>) : null;

  const degraded =
    iq && (Boolean(iq.competitor_landscape_degraded) || Number(iq.competitor_count) < 3);

  const hasDeepDives = peerDeepDives.length > 0;
  const deepPeerNorms = new Set(
    peerDeepDives.map((d) => normPeerLabel(String(d.peer_name ?? ""))).filter(Boolean),
  );
  const orphanMatrixRows = hasDeepDives
    ? matrix.filter((r) => !deepPeerNorms.has(normPeerLabel(String(r.peer_name ?? ""))))
    : matrix;

  const crossHorizonShort =
    shortPlan && Array.isArray(shortPlan.bullets)
      ? (shortPlan.bullets as string[]).filter((x) => String(x).trim())
      : [];
  const crossHorizonLong =
    longPlan && Array.isArray(longPlan.bullets)
      ? (longPlan.bullets as string[]).filter((x) => String(x).trim())
      : [];
  const hasCrossHorizonRollup = crossHorizonShort.length > 0 || crossHorizonLong.length > 0;

  const hasSupportingTables =
    matrix.length > 0 || moves.length > 0 || (hasDeepDives && hasCrossHorizonRollup);

  return (
    <div className="mx-auto max-w-5xl space-y-10 pb-8">
      <header className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-surface via-surface to-accent/[0.04] px-6 py-8 shadow-md shadow-slate-900/[0.05] ring-1 ring-border/60">
        <div
          className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-accent/10 blur-3xl"
          aria-hidden
        />
        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-accent">BattleScope</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-fg">Competitive strategy</h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
          Start with ranked moves, then open each deep-dive rival for stance and actions. Tables and extras stay at the bottom.
        </p>
      </header>

      {degraded ? (
        <div className="rounded-2xl border border-warning/30 border-l-4 border-l-warning bg-warning/[0.09] px-5 py-4 text-sm text-fg shadow-sm">
          <p className="font-semibold text-warning">Strategy may be directional only</p>
          {typeof iq?.notes === "string" && iq.notes ? <p className="mt-1.5 leading-relaxed text-muted">{iq.notes}</p> : null}
        </div>
      ) : null}

      <section className="space-y-6">
        <StrategySectionIntro
          chip="Top insights"
          title="What to prioritize next"
          description="Ranked strategic moves from the model. Tap a row to expand rationale, scope (time horizon and effort), and risk to your company. The first item starts open."
          accent="indigo"
        />
        {moves.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border bg-surface-elevated/40 px-4 py-6 text-center text-sm text-muted">
            No prioritized moves in this run.
          </p>
        ) : (
          <div className="rounded-2xl border border-border bg-surface px-4 py-1 shadow-sm ring-1 ring-border/40 sm:px-5">
            {moves.map((row, i) => (
              <PrioritizedMoveCard key={i} row={row} index={i} />
            ))}
          </div>
        )}
      </section>

      {hasDeepDives ? (
        <section className="space-y-6">
          <StrategySectionIntro
            chip="Rival lenses · 3 max"
            title="Company-by-company"
            description="One rival per card: stance in plain language, then short vs long actions. Extra axis rows stay under “Supporting axes” so this section stays readable."
            accent="indigo"
          />
          <div className="space-y-8">
            {peerDeepDives.map((row, i) => (
              <PeerDeepDiveCard
                key={i}
                row={row}
                index={i}
                total={peerDeepDives.length}
                matrixRows={matrixRowsForPeer(matrix, String(row.peer_name ?? ""))}
              />
            ))}
          </div>
        </section>
      ) : null}

      {!hasDeepDives ? (
        <section className="space-y-6">
          <StrategySectionIntro
            chip="Situation → implication"
            title="Competitive dynamics"
            description="Each card pairs what we see in the market (situation) with what it means for your company (implication), before deep-dive blocks are available."
            accent="violet"
          />
          {matrix.length === 0 ? (
            <p className="rounded-xl border border-dashed border-border bg-surface-elevated/40 px-4 py-6 text-center text-sm text-muted">
              No matrix rows yet. When the model emits peer deep dives, company-by-company cards will appear under Top moves.
            </p>
          ) : (
            <div className="space-y-5">
              {matrix.map((row, i) => (
                <MatrixInsightCard key={i} row={row} index={i} />
              ))}
            </div>
          )}
        </section>
      ) : orphanMatrixRows.length > 0 ? (
        <section className="space-y-6">
          <StrategySectionIntro
            chip="Matrix spillover"
            title="Additional axis-level dynamics"
            description="These rows did not attach to a named deep-dive peer—often a spelling mismatch or an extra competitor only in the advantage matrix."
            accent="slate"
          />
          <div className="space-y-5">
            {orphanMatrixRows.map((row, i) => (
              <MatrixInsightCard key={i} row={row} index={i} />
            ))}
          </div>
        </section>
      ) : null}

      {!hasDeepDives ? (
        <section>
          <StrategySectionIntro
            chip="Horizons"
            title="Cross-peer time horizons"
            description="Optional rollup themes that span multiple rivals—shown here when you do not yet have per-peer deep dive cards."
            accent="violet"
          />
          <div className="mt-5">
            <CrossPeerHorizons shortPlan={shortPlan} longPlan={longPlan} />
          </div>
        </section>
      ) : null}

      {crossPeerLevers.length > 0 ? (
        <section className="rounded-2xl border border-border bg-gradient-to-b from-surface to-surface-elevated/30 p-6 shadow-md shadow-slate-900/[0.04] ring-1 ring-border/50">
          <div className="mb-5">
            <span className="inline-flex rounded-full bg-surface-elevated px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-muted ring-1 ring-border">
              Cross-peer
            </span>
            <h2 className="mt-2 text-lg font-semibold tracking-tight text-fg">Where rivals align</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              A few themes many competitors push the same way—where you lag, and what to lean into next. Shown only when the model finds a grounded multi-peer pattern.
            </p>
          </div>
          <div className="space-y-4">
            {crossPeerLevers.slice(0, 3).map((row, i) => (
              <CrossPeerLeverCard key={i} row={row} />
            ))}
          </div>
        </section>
      ) : null}

      {hasSupportingTables ? (
        <details className="group rounded-2xl border border-dashed border-border bg-surface-elevated/35 shadow-sm ring-1 ring-border/40">
          <summary className="cursor-pointer list-none px-5 py-4 marker:content-none [&::-webkit-details-marker]:hidden">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-semibold text-fg group-open:text-accent">
                Supporting detail · tables & rollups
              </span>
              <span className="text-xs font-medium text-subtle">Expand</span>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-muted group-open:hidden">
              Full-width tables for copy-paste, plus cross-peer horizon bullets when applicable.
            </p>
          </summary>
          <div className="space-y-8 border-t border-border px-5 py-6">
            {hasDeepDives && hasCrossHorizonRollup ? (
              <div>
                <h3 className="mb-3 text-[10px] font-bold uppercase tracking-wide text-subtle">Cross-peer horizons</h3>
                <CrossPeerHorizons shortPlan={shortPlan} longPlan={longPlan} />
              </div>
            ) : null}
            {matrix.length > 0 ? (
              <div>
                <h3 className="mb-3 text-[10px] font-bold uppercase tracking-wide text-subtle">Advantage / gap matrix</h3>
                <FullMatrixTable matrix={matrix} />
              </div>
            ) : null}
            {moves.length > 0 ? (
              <div>
                <h3 className="mb-3 text-[10px] font-bold uppercase tracking-wide text-subtle">Prioritized moves</h3>
                <FullMovesTable moves={moves} />
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
}
