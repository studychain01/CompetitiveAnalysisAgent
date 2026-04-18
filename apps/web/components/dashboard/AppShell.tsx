"use client";

import type { RunSyncResponse } from "@/lib/types";
import { ActivityLog } from "./ActivityLog";
import { PipelineStepper } from "./PipelineStepper";
import { TargetSidebar } from "./TargetSidebar";
import { TabPanels } from "./TabPanels";
import { TabNav } from "./TabNav";

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

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-canvas text-fg">
      <div className="flex min-h-0 flex-1 gap-0">
        <aside className="flex w-[min(100%,320px)] shrink-0 flex-col gap-4 border-r border-border bg-surface p-4">
          <TargetSidebar displayName={displayName} url={url} />
          <PipelineStepper finalStage={isRunning ? null : run.stage} isRunning={isRunning} />
          <ActivityLog traceEvents={run.trace_events} plannerNotes={run.planner_notes} />
          <button
            type="button"
            onClick={onNewRun}
            className="shrink-0 rounded-lg border border-border py-2 text-sm font-medium text-muted transition hover:border-accent hover:text-accent"
          >
            New run
          </button>
        </aside>
        <main className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-2">
            <TabNav active={activeTab} onChange={onTabChange} />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            <TabPanels run={run} activeTab={activeTab} />
          </div>
        </main>
      </div>
    </div>
  );
}
