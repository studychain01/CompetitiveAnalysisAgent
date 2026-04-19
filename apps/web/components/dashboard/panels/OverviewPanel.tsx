import { pipelineStageForDisplay } from "@/lib/pipeline";
import type { RunSyncResponse } from "@/lib/types";

import { IntakeWaitHero } from "../IntakeWaitHero";

type Props = {
  run: RunSyncResponse;
  /** True while the SSE stream is active (used for first-paint intake experience). */
  isRunning?: boolean;
  /** Company name from the form when the profile artifact is still empty. */
  workingLabel?: string;
};

function hasOverviewContent(run: RunSyncResponse): boolean {
  const p = run.company_profile || {};
  const name = typeof p.name === "string" ? p.name.trim() : "";
  const summary = typeof p.summary === "string" ? p.summary.trim() : "";
  return Boolean(name || summary);
}

function getInputQuality(strategy: Record<string, unknown>) {
  const iq = strategy.input_quality;
  if (!iq || typeof iq !== "object") return null;
  return iq as Record<string, unknown>;
}

function asString(v: unknown): string {
  return typeof v === "string" ? v.trim() : "";
}

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function stringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string" && x.trim().length > 0).map((s) => s.trim());
}

function confidenceLabel(conf: unknown): string | null {
  if (typeof conf !== "number" || Number.isNaN(conf)) return null;
  const pct = Math.round(Math.max(0, Math.min(1, conf)) * 100);
  const band = conf >= 0.75 ? "High" : conf >= 0.45 ? "Medium" : "Low";
  return `${band} (${pct}%)`;
}

/** Value color for profile confidence row */
function confidenceValueClass(conf: unknown): string {
  if (typeof conf !== "number" || Number.isNaN(conf)) return "text-fg";
  if (conf >= 0.75) return "text-success";
  if (conf >= 0.45) return "text-warning";
  return "text-muted";
}

function chipCategory(text: string) {
  return (
    <span className="inline-flex items-center rounded-full border border-accent/25 bg-accent-subtle px-2.5 py-0.5 text-xs font-semibold text-accent">
      {text}
    </span>
  );
}

function chipDomain(text: string) {
  return (
    <span className="inline-flex items-center rounded-full border border-link/20 bg-canvas px-2.5 py-0.5 text-xs font-medium text-link">
      {text}
    </span>
  );
}

/** Gentle A/B rhythm: neutral pill vs barely-accented—stays board-deck quiet */
const ALT_CHIP_STYLES = [
  "border-border/80 bg-surface-elevated/70 text-muted",
  "border-accent/18 bg-accent-subtle/50 text-fg",
] as const;

function chipAlt(text: string, index: number) {
  const tone = ALT_CHIP_STYLES[index % ALT_CHIP_STYLES.length];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}
    >
      {text}
    </span>
  );
}

const LIST_CAP = 6;

function BulletList({ items, title, tone }: { items: string[]; title: string; tone: "strength" | "weakness" }) {
  const shown = items.slice(0, LIST_CAP);
  const rest = items.length - shown.length;
  const bar =
    tone === "strength"
      ? "border-l-[3px] border-l-success/45"
      : "border-l-[3px] border-l-warning/50";
  const heading =
    tone === "strength" ? "text-success" : "text-warning";
  const marker = tone === "strength" ? "marker:text-success/70" : "marker:text-warning/80";
  return (
    <section className={`rounded-2xl border border-border bg-surface p-5 pl-[1.125rem] shadow-sm ${bar}`}>
      <h2 className={`text-xs font-semibold uppercase tracking-wider ${heading}`}>{title}</h2>
      <ul className={`mt-3 list-inside list-disc space-y-2 text-sm leading-relaxed text-fg ${marker}`}>
        {shown.map((t, i) => (
          <li key={i} className="pl-0.5">
            {t}
          </li>
        ))}
      </ul>
      {rest > 0 ? <p className="mt-2 text-xs text-muted">+{rest} more</p> : null}
    </section>
  );
}

function UncertaintiesList({ items }: { items: string[] }) {
  const shown = items.slice(0, LIST_CAP);
  const rest = items.length - shown.length;
  return (
    <section className="rounded-2xl border border-border border-l-[3px] border-l-accent/40 bg-accent-subtle/40 px-5 py-4 shadow-sm">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-accent">Uncertainties</h2>
      <ul className="mt-3 space-y-2 text-sm leading-relaxed text-fg">
        {shown.map((t, i) => (
          <li key={i} className="flex gap-2">
            <span className="text-subtle" aria-hidden>
              ·
            </span>
            <span>{t}</span>
          </li>
        ))}
      </ul>
      {rest > 0 ? <p className="mt-2 text-xs text-muted">+{rest} more</p> : null}
    </section>
  );
}

export function OverviewPanel({ run, isRunning = false, workingLabel = "" }: Props) {
  if (isRunning && !hasOverviewContent(run)) {
    return <IntakeWaitHero workingLabel={workingLabel} />;
  }

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

  const domain =
    (typeof profile.primary_domain === "string" && profile.primary_domain) ||
    (typeof run.company_url_normalized === "string" && run.company_url_normalized) ||
    "";

  const buyerRaw = asString(profile.buyer);
  const buyer =
    buyerRaw && buyerRaw.toLowerCase() !== "unknown" ? buyerRaw : "";

  const ec = asRecord(profile.earnings_call);
  const symbol = ec ? asString(ec.symbol) : "";
  const quarter = ec ? asString(ec.quarter) : "";
  const tickerQuarter =
    symbol || quarter
      ? [symbol, quarter].filter(Boolean).join(" · ")
      : "";

  const confLabel = confidenceLabel(profile.profile_confidence);
  const altCats = stringArray(profile.category_alternatives);

  const strengths = ec ? stringArray(ec.strengths) : [];
  const weaknesses = ec ? stringArray(ec.weaknesses) : [];
  const uncertainties = stringArray(profile.uncertainties);

  const hasGlanceRow = Boolean(buyer || tickerQuarter || confLabel);
  const hasAltCats = altCats.length > 0;

  const businessModel =
    typeof profile.business_model === "string" && profile.business_model.trim() && profile.business_model !== "unknown"
      ? profile.business_model.trim()
      : "";

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-fg">
              {typeof profile.name === "string" && profile.name ? profile.name : "Company"}
            </h1>
            <div className="mt-3 flex flex-wrap gap-2">
              {typeof profile.category === "string" && profile.category ? chipCategory(profile.category) : null}
              {domain ? chipDomain(domain) : null}
            </div>
          </div>
          <div className="rounded-xl bg-accent-subtle px-4 py-3 text-center sm:min-w-[140px]">
            <p className="text-xs font-semibold uppercase tracking-wide text-accent">Pipeline stage</p>
            <p className="mt-1 font-mono text-sm font-medium text-fg">
              {pipelineStageForDisplay(run.stage || "", isRunning) || "—"}
            </p>
          </div>
        </div>

        {hasGlanceRow || hasAltCats ? (
          <div className="mt-6 rounded-xl border border-border bg-surface-elevated/60 px-4 py-4 sm:px-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-subtle">At a glance</p>
            {hasGlanceRow ? (
              <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-[minmax(7.5rem,auto)_1fr] sm:gap-y-2.5">
                {buyer ? (
                  <>
                    <dt className="text-xs font-medium text-subtle sm:pt-0.5">Buyer</dt>
                    <dd className="text-sm font-medium text-fg">{buyer}</dd>
                  </>
                ) : null}
                {tickerQuarter ? (
                  <>
                    <dt className="text-xs font-medium text-subtle sm:pt-0.5">Ticker / quarter</dt>
                    <dd className="font-mono text-sm text-fg">{tickerQuarter}</dd>
                  </>
                ) : null}
                {confLabel ? (
                  <>
                    <dt className="text-xs font-medium text-subtle sm:pt-0.5">Profile confidence</dt>
                    <dd className={`text-sm font-semibold ${confidenceValueClass(profile.profile_confidence)}`}>
                      {confLabel}
                    </dd>
                  </>
                ) : null}
              </dl>
            ) : null}
            {hasAltCats ? (
              <div className={hasGlanceRow ? "mt-4 border-t border-border pt-4" : "mt-3"}>
                <p className="text-xs font-medium text-subtle">Alternate categories</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {altCats.map((c, i) => (
                    <span key={c}>{chipAlt(c, i)}</span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {businessModel ? (
          <div className="mt-6 border-t border-border pt-6">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-subtle">How they make money</h2>
            <p className="mt-3 max-w-prose text-[15px] leading-relaxed text-fg">{businessModel}</p>
          </div>
        ) : null}
      </section>

      {strengths.length > 0 || weaknesses.length > 0 ? (
        <div
          className={
            strengths.length > 0 && weaknesses.length > 0
              ? "grid gap-6 sm:grid-cols-2"
              : "grid gap-6"
          }
        >
          {strengths.length > 0 ? <BulletList items={strengths} title="Strengths" tone="strength" /> : null}
          {weaknesses.length > 0 ? <BulletList items={weaknesses} title="Weaknesses" tone="weakness" /> : null}
        </div>
      ) : null}

      {uncertainties.length > 0 ? <UncertaintiesList items={uncertainties} /> : null}

      {degraded ? (
        <div
          className="rounded-xl border-l-4 border-warning bg-warning/10 px-4 py-3 text-sm text-fg shadow-sm"
          role="status"
        >
          <p className="font-semibold text-warning">Partial or degraded inputs</p>
          {iqNotes ? <p className="mt-1 text-muted">{iqNotes}</p> : null}
        </div>
      ) : null}

      {stratStatus && stratStatus !== "ok" ? (
        <div
          className={`rounded-xl border-l-4 px-4 py-3 text-sm shadow-sm ${
            stratStatus === "error"
              ? "border-danger bg-danger/10 text-fg"
              : stratStatus === "skipped"
                ? "border-border bg-surface-elevated text-muted"
                : "border-warning bg-warning/10 text-fg"
          }`}
          role="status"
        >
          <p className="font-semibold">
            Strategy: <span className="font-mono font-normal">{stratStatus}</span>
          </p>
          {stratReason ? <p className="mt-1 text-muted">{stratReason}</p> : null}
        </div>
      ) : null}

      <section className="rounded-2xl border border-border border-t-[3px] border-t-accent/35 bg-surface p-6 shadow-sm">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-accent">Executive summary</h2>
        {summary ? (
          <p className="mt-4 max-w-prose whitespace-pre-wrap text-base leading-relaxed text-fg">{summary}</p>
        ) : (
          <p className="mt-4 text-sm text-muted">No summary returned for this run yet.</p>
        )}
      </section>
    </div>
  );
}
