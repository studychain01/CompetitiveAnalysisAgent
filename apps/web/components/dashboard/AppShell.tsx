"use client";

import { useMemo } from "react";

import type { RunSyncResponse } from "@/lib/types";
import { getTabUiState, type TabId, type TabUiState } from "@/lib/tab-stage";

import { ActivityLog } from "./ActivityLog";
import { PipelineStepper } from "./PipelineStepper";
import { TargetSidebar } from "./TargetSidebar";
import { TAB_IDS, TabNav } from "./TabNav";
import { TabPanels } from "./TabPanels";

type AppShellProps = {
  run: RunSyncResponse;
  submittedName: string;
  submittedUrl: string;
  isRunning: boolean;
  activeTab: string;
  onTabChange: (tab: string) => void;
  onNewRun: () => void;
};

export function AppShell({
  run,
  submittedName,
  submittedUrl,
  isRunning,
  activeTab,
  onTabChange,
  onNewRun,
}: AppShellProps) {
  const profile = run.company_profile || {};
  const displayName =
    (typeof profile.name === "string" && profile.name) || submittedName || "Company";
  const url =
    (run.company_url_normalized as string | undefined) ||
    (typeof profile.url === "string" && profile.url) ||
    submittedUrl;

  const tabStates = useMemo(() => {
    const ctx = { stage: run.stage || "", isRunning, run };
    const out = {} as Record<TabId, TabUiState>;
    for (const id of TAB_IDS) {
      out[id] = getTabUiState(id, ctx);
    }
    return out;
  }, [run, isRunning]);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-canvas text-fg">
      <div className="flex min-h-0 flex-1 gap-0">
        <aside className="flex w-[min(100%,320px)] shrink-0 flex-col gap-4 border-r border-border bg-surface p-4 shadow-sm">
          <TargetSidebar displayName={displayName} url={url} />
          <PipelineStepper finalStage={run.stage || null} isRunning={isRunning} />
          <details className="group min-h-0 rounded-lg border border-dashed border-border bg-surface-elevated/40">
            <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold text-muted marker:content-none [&::-webkit-details-marker]:hidden">
              <span className="text-subtle group-open:text-fg">Technical log</span>
              <span className="ml-1 text-[10px] font-normal text-subtle">(optional)</span>
            </summary>
            <div className="border-t border-border px-2 pb-2">
              <ActivityLog
                traceEvents={run.trace_events}
                plannerNotes={run.planner_notes}
                embedded
              />
            </div>
          </details>
          <button
            type="button"
            onClick={onNewRun}
            className="shrink-0 rounded-lg border border-border py-2 text-sm font-medium text-muted transition hover:border-accent hover:text-accent"
          >
            New run
          </button>
        </aside>
        <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-canvas">
          <div className="flex shrink-0 items-center justify-between border-b border-border bg-surface px-4 py-2">
            <TabNav active={activeTab} tabStates={tabStates} onChange={onTabChange} />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            <TabPanels
              run={run}
              activeTab={activeTab}
              isRunning={isRunning}
              workingLabel={submittedName}
            />
          </div>
        </main>
      </div>
    </div>
  );
}
