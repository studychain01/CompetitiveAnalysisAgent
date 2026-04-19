/**
 * Human-readable status while the pipeline is executing (replaces raw trace noise in chrome).
 */

export function runningStageMessage(stage: string): string {
  const s = (stage || "").trim();
  switch (s) {
    case "intake":
      return "Building your company profile…";
    case "sec_risk":
      return "Reviewing SEC risk themes…";
    case "competitor_discover":
      return "Mapping the competitive landscape…";
    case "peer_research_parallel":
      return "Running competitor deep dives…";
    case "competitive_strategy":
      return "Synthesizing strategy…";
    default:
      return "Starting your research run…";
  }
}
