/** Backend `stage` ids after each node (see graph builder). */
export const PIPELINE_STAGES = [
  { id: "intake", label: "Company profile" },
  { id: "sec_risk", label: "SEC risk" },
  { id: "competitor_discover", label: "Competitors" },
  { id: "peer_research_parallel", label: "Deep dives" },
  { id: "competitive_strategy", label: "Strategy" },
] as const;

export type PipelineStageId = (typeof PIPELINE_STAGES)[number]["id"];

export function stageIndex(stage: string): number {
  const i = PIPELINE_STAGES.findIndex((s) => s.id === stage);
  return i === -1 ? 0 : i;
}

/**
 * LangGraph updates `stage` when a node **finishes**. While the **next** node is executing, `stage` still
 * holds the previous step id—so UI that shows "what is running" must look one step ahead.
 */
export function executingPipelineStageId(completedOrReportedStage: string): PipelineStageId {
  const s = (completedOrReportedStage || "").trim();
  const i = PIPELINE_STAGES.findIndex((x) => x.id === s);
  if (i === -1) {
    return PIPELINE_STAGES[0].id;
  }
  if (i >= PIPELINE_STAGES.length - 1) {
    return PIPELINE_STAGES[PIPELINE_STAGES.length - 1].id;
  }
  return PIPELINE_STAGES[i + 1].id;
}

/** Stage id to show in badges / header while streaming (executing node), or raw `stage` when idle. */
export function pipelineStageForDisplay(completedStage: string, isRunning: boolean): string {
  if (!isRunning) return (completedStage || "").trim();
  return executingPipelineStageId(completedStage);
}
