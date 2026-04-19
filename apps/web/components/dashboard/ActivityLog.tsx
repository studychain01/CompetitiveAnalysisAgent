import type { TraceEvent } from "@/lib/types";

type ActivityLogProps = {
  traceEvents: TraceEvent[];
  plannerNotes: string[];
  /** Tighter layout when nested under a disclosure (sidebar). */
  embedded?: boolean;
};

export function ActivityLog({ traceEvents, plannerNotes, embedded }: ActivityLogProps) {
  const clip = (s: string, max: number) => (s.length <= max ? s : `${s.slice(0, max)}…`);

  const lines: string[] = [
    ...traceEvents.map((ev) => {
      const raw =
        ev.payload && Object.keys(ev.payload).length ? ` ${JSON.stringify(ev.payload)}` : "";
      const extra = clip(raw, 800);
      return clip(`${ev.event_type}: ${ev.message}${extra}`, 2000);
    }),
    ...plannerNotes.map((n) => `note: ${n}`),
  ];

  return (
    <section
      className={`flex min-h-0 flex-col rounded-lg border border-border bg-surface ${embedded ? "" : "flex-1"}`}
    >
      {!embedded ? (
        <h2 className="shrink-0 border-b border-border px-3 py-2 text-xs font-semibold uppercase tracking-wide text-subtle">
          Activity
        </h2>
      ) : null}
      <div
        className={`overflow-y-auto font-mono leading-relaxed text-muted ${embedded ? "max-h-40 p-2 text-[10px]" : "min-h-[120px] flex-1 p-3 text-[11px]"}`}
        role="log"
        aria-live="polite"
      >
        {lines.length === 0 ? (
          <p className="text-subtle">No trace events yet.</p>
        ) : (
          <ul className="space-y-1">
            {lines.map((line, i) => (
              <li key={i} className="flex gap-2 break-words">
                <span className="shrink-0 text-success">✓</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
