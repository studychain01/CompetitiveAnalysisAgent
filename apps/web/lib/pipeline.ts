/** Backend `stage` ids after each node (see graph builder). */
export const PIPELINE_STAGES = [
  { id: "intake", label: "Company profile" },
  { id: "sec_risk", label: "SEC risk" },
  { id: "competitor_discover", label: "Competitors" },
  { id: "peer_research_parallel", label: "Peer deep-dives" },
  { id: "competitive_strategy", label: "Strategy" },
] as const;

export type PipelineStageId = (typeof PIPELINE_STAGES)[number]["id"];

export function stageIndex(stage: string): number {
  const i = PIPELINE_STAGES.findIndex((s) => s.id === stage);
  return i === -1 ? 0 : i;
}
