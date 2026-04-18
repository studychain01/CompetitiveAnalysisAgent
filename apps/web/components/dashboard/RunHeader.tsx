"use client";

type RunHeaderProps = {
  runId: string | null;
  elapsedSeconds: number;
  live: boolean;
};

export function RunHeader({ runId, elapsedSeconds, live }: RunHeaderProps) {
  const mm = Math.floor(elapsedSeconds / 60);
  const ss = elapsedSeconds % 60;
  const elapsedLabel = `${mm}:${ss.toString().padStart(2, "0")}`;

  return (
    <header className="flex shrink-0 items-center justify-between border-b border-border px-5 py-3">
      <div className="flex items-center gap-3">
        <span className="text-lg font-semibold tracking-tight text-fg">BattleScope</span>
        <span
          className={
            live
              ? "inline-flex items-center gap-1.5 rounded-full bg-accent-subtle px-2.5 py-0.5 text-xs font-medium text-accent"
              : "inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-xs font-medium text-muted"
          }
        >
          <span
            className={
              live ? "h-1.5 w-1.5 animate-pulse rounded-full bg-success" : "h-1.5 w-1.5 rounded-full bg-subtle"
            }
            aria-hidden
          />
          {live ? "live" : "idle"}
        </span>
      </div>
      <div className="flex items-center gap-6 text-sm text-muted">
        {runId ? (
          <span>
            run <code className="font-mono text-fg">{runId.slice(0, 8)}</code>
          </span>
        ) : (
          <span className="text-subtle">no run</span>
        )}
        <span>
          elapsed <span className="font-mono text-fg">{elapsedLabel}</span>
        </span>
      </div>
    </header>
  );
}
