"use client";

import { executingPipelineStageId, PIPELINE_STAGES, stageIndex } from "@/lib/pipeline";

type PipelineStepperProps = {
  finalStage: string | null;
  isRunning: boolean;
};

export function PipelineStepper({ finalStage, isRunning }: PipelineStepperProps) {
  const idxDone = finalStage ? stageIndex(finalStage) : -1;
  /** Pipeline node currently executing (``stage`` from API is last *completed*). */
  const execId = isRunning ? executingPipelineStageId(finalStage || "") : "";
  const execIdx = isRunning ? stageIndex(execId) : -1;

  return (
    <section className="rounded-lg border border-border bg-surface-elevated p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-subtle">Pipeline</h2>
      <ol className="mt-3 space-y-0">
        {PIPELINE_STAGES.map((step, i) => {
          const done = isRunning ? i < execIdx : idxDone >= 0 && i <= idxDone;
          const active = isRunning && i === execIdx;

          return (
            <li key={step.id} className="flex gap-3 border-l border-border py-2 pl-3 first:pt-0 last:pb-0">
              <div className="relative -ml-[calc(0.75rem+1px)] flex w-4 shrink-0 justify-center">
                <span
                  className={
                    done
                      ? "mt-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-success/20 text-xs text-success"
                      : active
                        ? "mt-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2 border-accent bg-accent-subtle animate-pulse-ring"
                        : "mt-0.5 flex h-4 w-4 items-center justify-center rounded-full border border-border bg-surface"
                  }
                  aria-hidden
                >
                  {done ? "✓" : ""}
                </span>
              </div>
              <div className="min-w-0 flex-1">
                <p
                  className={
                    !done && !active
                      ? "text-sm text-subtle"
                      : active
                        ? "text-sm font-medium text-accent"
                        : "text-sm font-medium text-fg"
                  }
                >
                  {step.label}
                </p>
                <p className="font-mono text-[10px] text-subtle">{step.id}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
