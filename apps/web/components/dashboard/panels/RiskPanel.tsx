import type { ReactNode } from "react";

import type { RunSyncResponse } from "@/lib/types";

type Props = {
  run: RunSyncResponse;
};

/** Mirrors API ``RISK_THEME_CATEGORY_ORDER`` for stable section order. */
const RISK_CATEGORY_ORDER = [
  "Competition",
  "Demand/Macro",
  "Supply chain",
  "Regulatory",
  "Cyber/IP",
  "Operational",
  "Financial/Liquidity",
  "Legal/Litigation",
  "People",
  "Strategy/Execution",
  "Other",
] as const;

const LONG_BULLET_THRESHOLD = 240;

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function asString(v: unknown): string {
  return typeof v === "string" ? v.trim() : "";
}

type IndexedBullet = { index: number; text: string; headline?: string };

function previewForDetails(text: string, maxLen = 140): string {
  const t = text.trim();
  if (t.length <= maxLen) return t;
  const shortened = t.slice(0, maxLen).trim();
  const lastSpace = shortened.lastIndexOf(" ");
  return (lastSpace > 48 ? shortened.slice(0, lastSpace) : shortened) + "…";
}

function RiskBulletCard({ item }: { item: IndexedBullet }) {
  const text = item.text;
  const headline = item.headline?.trim();

  if (headline) {
    return (
      <li className="rounded-xl border border-border bg-surface-elevated/60 shadow-sm">
        <details className="group">
          <summary className="cursor-pointer list-none px-4 py-3 [&::-webkit-details-marker]:hidden">
            <div className="flex flex-col gap-1.5">
              <span className="text-base font-semibold leading-snug text-fg">{headline}</span>
              <span className="text-xs font-medium text-accent group-open:hidden">Show full theme</span>
              <span className="hidden text-xs font-medium text-accent group-open:inline">Hide full theme</span>
            </div>
          </summary>
          <div className="border-t border-border px-4 py-3">
            <p className="text-sm leading-relaxed text-fg">{text}</p>
          </div>
        </details>
      </li>
    );
  }

  const useDetails = text.length > LONG_BULLET_THRESHOLD;

  if (useDetails) {
    return (
      <li className="rounded-xl border border-border bg-surface-elevated/60 shadow-sm">
        <details className="group">
          <summary className="cursor-pointer list-none px-4 py-3 [&::-webkit-details-marker]:hidden">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-sm leading-relaxed text-fg">{previewForDetails(text)}</span>
              <span className="text-xs font-medium text-accent group-open:hidden">Show full</span>
              <span className="hidden text-xs font-medium text-accent group-open:inline">Hide</span>
            </div>
          </summary>
          <div className="border-t border-border px-4 py-3">
            <p className="text-sm leading-relaxed text-fg">{text}</p>
          </div>
        </details>
      </li>
    );
  }

  return (
    <li className="rounded-xl border border-border bg-surface-elevated/60 px-4 py-3 text-sm leading-relaxed text-fg shadow-sm">
      {text}
    </li>
  );
}

function FilingSourceStrip({ dossier }: { dossier: Record<string, unknown> }) {
  const filing = asRecord(dossier.filing);
  const extraction = asRecord(dossier.extraction);
  const symbol = asString(dossier.symbol);
  const finalLink = filing ? asString(filing.final_link) : "";
  const formType = filing ? asString(filing.form_type) : "";
  const filingDate = filing ? asString(filing.filing_date) : "";
  const method = extraction ? asString(extraction.method) : "";
  const confidence = extraction ? asString(extraction.confidence) : "";

  if (!finalLink && !formType && !filingDate && !symbol && !method && !confidence) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-border border-l-[3px] border-l-accent/45 bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-accent">10-K source</p>
      <div className="mt-3 flex flex-col gap-2 text-sm text-fg sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6">
        {symbol ? (
          <p>
            <span className="text-subtle">Symbol</span>{" "}
            <span className="font-mono font-semibold">{symbol}</span>
          </p>
        ) : null}
        {formType || filingDate ? (
          <p>
            <span className="text-subtle">Filing</span>{" "}
            <span className="font-medium">
              {[formType, filingDate].filter(Boolean).join(" · ") || "—"}
            </span>
          </p>
        ) : null}
        {finalLink ? (
          <a
            href={finalLink}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 font-medium text-link hover:underline"
          >
            Open 10-K
            <span aria-hidden>↗</span>
          </a>
        ) : null}
      </div>
      {method || confidence ? (
        <p className="mt-3 text-xs text-muted">
          Item 1A extraction
          {method ? (
            <>
              : <span className="font-mono">{method}</span>
            </>
          ) : null}
          {confidence ? (
            <>
              {" "}
              · confidence <span className="font-medium">{confidence}</span>
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}

function groupBulletsByCategory(
  bullets: string[],
  categories: string[] | null,
  headlines: string[] | null,
): Map<string, IndexedBullet[]> | null {
  if (!categories || categories.length !== bullets.length) return null;
  const headsOk = headlines && headlines.length === bullets.length;
  const map = new Map<string, IndexedBullet[]>();
  bullets.forEach((raw, i) => {
    const text = String(raw).trim();
    if (!text) return;
    const cat = categories[i] || "Other";
    const h = headsOk ? String(headlines![i] ?? "").trim() : "";
    const list = map.get(cat) ?? [];
    list.push({ index: i, text, ...(h ? { headline: h } : {}) });
    map.set(cat, list);
  });
  return map;
}

function groupedRiskSections(grouped: Map<string, IndexedBullet[]>): ReactNode[] {
  const used = new Set<string>();
  const sections: ReactNode[] = [];
  for (const category of RISK_CATEGORY_ORDER) {
    const items = grouped.get(category);
    if (!items?.length) continue;
    used.add(category);
    sections.push(
      <section
        key={category}
        className="rounded-2xl border border-border border-l-[3px] border-l-accent/40 bg-surface p-6 shadow-sm"
      >
        <h2 className="text-sm font-semibold tracking-tight text-accent">{category}</h2>
        <ul className="mt-4 space-y-3">
          {items.map((item) => (
            <RiskBulletCard key={item.index} item={item} />
          ))}
        </ul>
      </section>,
    );
  }
  for (const [category, items] of grouped.entries()) {
    if (used.has(category) || !items.length) continue;
    sections.push(
      <section
        key={category}
        className="rounded-2xl border border-border border-l-[3px] border-l-muted/50 bg-surface p-6 shadow-sm"
      >
        <h2 className="text-sm font-semibold tracking-tight text-muted">{category}</h2>
        <ul className="mt-4 space-y-3">
          {items.map((item) => (
            <RiskBulletCard key={item.index} item={item} />
          ))}
        </ul>
      </section>,
    );
  }
  return sections;
}

function bulletItem(
  i: number,
  text: string,
  headlinesAligned: string[] | null,
): IndexedBullet {
  const h = headlinesAligned?.[i]?.trim();
  return { index: i, text, ...(h ? { headline: h } : {}) };
}

export function RiskPanel({ run }: Props) {
  const d = run.sec_risk_dossier || {};
  const status = typeof d.status === "string" ? d.status : "unknown";
  const reason = typeof d.reason === "string" ? d.reason : "";
  const bullets = Array.isArray(d.risk_theme_bullets) ? (d.risk_theme_bullets as unknown[]).map(String) : [];
  const rawCats = Array.isArray(d.risk_theme_categories) ? (d.risk_theme_categories as unknown[]).map(String) : null;
  const rawHeads = Array.isArray(d.risk_theme_headlines) ? (d.risk_theme_headlines as unknown[]).map(String) : null;
  const categoriesAligned =
    rawCats && rawCats.length === bullets.length ? rawCats.map((c) => c.trim() || "Other") : null;
  const headlinesAligned =
    rawHeads && rawHeads.length === bullets.length ? rawHeads.map((h) => String(h).trim()) : null;
  const grouped = groupBulletsByCategory(bullets, categoriesAligned, headlinesAligned);

  const isError = status === "error" || status === "skipped";
  const isPartial = status === "partial";

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div
        className={`rounded-2xl border px-5 py-4 text-sm shadow-sm ${
          isError
            ? "border-danger/40 bg-danger/10"
            : isPartial
              ? "border-warning/40 bg-warning/10"
              : "border-border bg-surface shadow-sm"
        }`}
      >
        <p className="font-semibold text-fg">
          Status: <span className="font-mono font-normal text-muted">{status}</span>
        </p>
        {reason ? <p className="mt-2 leading-relaxed text-muted">{reason}</p> : null}
      </div>

      {status === "skipped" && bullets.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface-elevated/80 px-6 py-10 text-center">
          <div
            className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-accent-subtle text-xl text-accent"
            aria-hidden
          >
            ◆
          </div>
          <p className="text-base font-medium text-fg">10-K risk themes not generated</p>
          <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted">
            Usually this means no equity ticker was found on the profile yet. After intake fills{" "}
            <code className="rounded bg-canvas px-1 font-mono text-xs">earnings_call.symbol</code>, re-run to pull Item
            1A themes.
          </p>
        </div>
      ) : null}

      {bullets.length > 0 ? <FilingSourceStrip dossier={d as Record<string, unknown>} /> : null}

      {bullets.length === 0 ? (
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-subtle">10-K risk themes</h2>
          <p className="mt-4 text-sm text-muted">No risk theme bullets in this dossier.</p>
        </section>
      ) : grouped ? (
        <div className="space-y-8">{groupedRiskSections(grouped)}</div>
      ) : (
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-subtle">10-K risk themes</h2>
          <ol className="mt-4 space-y-3">
            {bullets.map((b, i) => (
              <RiskBulletCard key={i} item={bulletItem(i, String(b).trim(), headlinesAligned)} />
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
