/**
 * Tab gating vs LangGraph `stage` (see `pipeline.ts`).
 *
 * | Tab        | Running tab highlights when | Unlocks (ready) when |
 * |------------|------------------------------|------------------------|
 * | overview   | **Executing** intake (or `stage` empty) | Profile has name/summary, or stage past intake |
 * | risk       | **Executing** sec_risk       | Past sec_risk + dossier has `status` |
 * | competitors | **Executing** competitor_discover | Past discover + landscape has data |
 * | peers (UI: Deep dives) | **Executing** peer_research_parallel | Past parallel + digest batch has `status` or `by_peer` |
 * | strategy   | **Executing** competitive_strategy | Past strategy node + strategy artifact has content or `status` |
 *
 * ``stage`` on the wire is the **last completed** node; while ``isRunning``, we map the **next** pipeline id
 * (see ``executingPipelineStageId`` in ``pipeline.ts``) so tabs match the sidebar stepper.
 */

import type { RunSyncResponse } from "@/lib/types";

import { executingPipelineStageId, stageIndex } from "./pipeline";

export type TabId = "overview" | "risk" | "competitors" | "peers" | "strategy";
export type TabUiState = "locked" | "running" | "ready";

const STAGE_TO_TAB: Record<string, TabId> = {
  intake: "overview",
  sec_risk: "risk",
  competitor_discover: "competitors",
  peer_research_parallel: "peers",
  competitive_strategy: "strategy",
};

export function sliceRunningTab(stage: string, isRunning: boolean): TabId | null {
  if (!isRunning) return null;
  const exec = executingPipelineStageId(stage);
  return STAGE_TO_TAB[exec] ?? "overview";
}

function trimStr(v: unknown): string {
  return typeof v === "string" ? v.trim() : "";
}

function overviewReady(run: RunSyncResponse, stage: string): boolean {
  const p = run.company_profile || {};
  const hasProfile = Boolean(trimStr(p.name) || trimStr(p.summary));
  return hasProfile || stageIndex(stage) >= 1;
}

function riskReady(run: RunSyncResponse, stage: string): boolean {
  if (stageIndex(stage) < 1) return false;
  const d = run.sec_risk_dossier || {};
  return typeof d.status === "string";
}

function competitorsReady(run: RunSyncResponse, stage: string): boolean {
  if (stageIndex(stage) < 2) return false;
  const L = run.competitor_landscape || {};
  const comps = L.competitors;
  if (Array.isArray(comps) && comps.length > 0) return true;
  return stageIndex(stage) >= 3;
}

function peersReady(run: RunSyncResponse, stage: string): boolean {
  if (stageIndex(stage) < 3) return false;
  const d = run.peer_research_digests || {};
  const by = d.by_peer;
  if (by && typeof by === "object" && !Array.isArray(by) && Object.keys(by as object).length > 0) return true;
  return stageIndex(stage) >= 4;
}

function strategyReady(run: RunSyncResponse, stage: string): boolean {
  if (stageIndex(stage) < 4) return false;
  const s = run.competitive_strategy || {};
  if (trimStr(s.executive_summary)) return true;
  const dives = s.peer_deep_dives;
  if (Array.isArray(dives) && dives.length > 0) return true;
  const matrix = s.advantage_gap_matrix;
  const moves = s.prioritized_moves;
  if (Array.isArray(matrix) && matrix.length > 0) return true;
  if (Array.isArray(moves) && moves.length > 0) return true;
  return typeof s.status === "string" && stageIndex(stage) >= 4;
}

function tabReady(tab: TabId, run: RunSyncResponse, stage: string): boolean {
  switch (tab) {
    case "overview":
      return overviewReady(run, stage);
    case "risk":
      return riskReady(run, stage);
    case "competitors":
      return competitorsReady(run, stage);
    case "peers":
      return peersReady(run, stage);
    case "strategy":
      return strategyReady(run, stage);
    default:
      return false;
  }
}

export function getTabUiState(
  tab: TabId,
  ctx: { stage: string; isRunning: boolean; run: RunSyncResponse },
): TabUiState {
  const { stage, isRunning, run } = ctx;
  const runningTab = sliceRunningTab(stage, isRunning);
  if (isRunning && runningTab === tab) return "running";
  if (tabReady(tab, run, stage)) return "ready";
  return "locked";
}

const TAB_ORDER: TabId[] = ["overview", "risk", "competitors", "peers", "strategy"];

export function getFirstReadyTab(ctx: { stage: string; isRunning: boolean; run: RunSyncResponse }): TabId {
  for (const id of TAB_ORDER) {
    if (getTabUiState(id, ctx) === "ready") return id;
  }
  return "overview";
}

/** First tab that is not locked (``running`` or ``ready``); fallback ``overview``. */
export function getFirstUnlockedTab(ctx: { stage: string; isRunning: boolean; run: RunSyncResponse }): TabId {
  for (const id of TAB_ORDER) {
    if (getTabUiState(id, ctx) !== "locked") return id;
  }
  return "overview";
}

export function tabTooltip(tab: TabId, state: TabUiState): string | undefined {
  if (state !== "locked") return undefined;
  switch (tab) {
    case "overview":
      return "Available when the company profile is ready.";
    case "risk":
      return "Available after SEC risk step.";
    case "competitors":
      return "Available after competitor discovery.";
    case "peers":
      return "Available after deep-dive competitor research completes.";
    case "strategy":
      return "Available when strategy synthesis completes.";
    default:
      return "Locked until upstream steps finish.";
  }
}
