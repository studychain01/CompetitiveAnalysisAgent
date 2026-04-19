"use client";

import { executingPipelineStageId } from "@/lib/pipeline";
import { runningStageMessage } from "@/lib/run-status";

type RunHeaderProps = {
  runId: string | null;
  elapsedSeconds: number;
  live: boolean;
  /** Backend graph `stage` while a run exists; used for human status copy when `live`. */
  pipelineStage?: string;
};

export function RunHeader({ runId, elapsedSeconds, live, pipelineStage = "" }: RunHeaderProps) {
  const mm = Math.floor(elapsedSeconds / 60);
  const ss = elapsedSeconds % 60;
  const elapsedLabel = `${mm}:${ss.toString().padStart(2, "0")}`;
  const statusStage = live ? executingPipelineStageId(pipelineStage) : pipelineStage;
  const statusText = runningStageMessage(statusStage);

  return (
    <header
      className="flex shrink-0 items-center gap-4 border-b border-border bg-surface px-4 py-3 shadow-sm sm:px-5"
      aria-busy={live}
    >
      <div className="flex shrink-0 items-center gap-3">
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

      {live ? (
        <div
          className="flex min-w-0 flex-1 items-center justify-center gap-2.5 px-2"
          role="status"
          aria-live="polite"
          aria-relevant="text"
        >
          <span
            className="h-4 w-4 shrink-0 rounded-full border-2 border-accent/30 border-t-accent animate-spin"
            aria-hidden
          />
          <span className="truncate text-center text-sm font-medium text-muted">{statusText}</span>
        </div>
      ) : (
        <div className="min-w-0 flex-1" />
      )}

      <div className="flex shrink-0 flex-col items-end gap-0.5 text-sm text-muted sm:flex-row sm:items-center sm:gap-6">
        {runId ? (
          <span className="hidden sm:inline">
            run <code className="font-mono text-fg">{runId.slice(0, 8)}</code>
          </span>
        ) : (
          <span className="hidden text-subtle sm:inline">no run</span>
        )}
        <span>
          <span className="sm:hidden">⏱ </span>
          <span className="font-mono text-fg">{elapsedLabel}</span>
        </span>
      </div>
    </header>
  );
}
