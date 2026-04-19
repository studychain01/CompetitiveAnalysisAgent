"use client";

import type { RunSyncResponse } from "@/lib/types";
import { CompetitorsPanel } from "./panels/CompetitorsPanel";
import { OverviewPanel } from "./panels/OverviewPanel";
import { PeersPanel } from "./panels/PeersPanel";
import { RiskPanel } from "./panels/RiskPanel";
import { StrategyPanel } from "./panels/StrategyPanel";

type TabPanelsProps = {
  run: RunSyncResponse;
  activeTab: string;
  isRunning: boolean;
  workingLabel: string;
};

export function TabPanels({ run, activeTab, isRunning, workingLabel }: TabPanelsProps) {
  switch (activeTab) {
    case "risk":
      return <RiskPanel run={run} />;
    case "competitors":
      return <CompetitorsPanel run={run} />;
    case "peers":
      return <PeersPanel run={run} />;
    case "strategy":
      return <StrategyPanel run={run} />;
    case "overview":
    default:
      return <OverviewPanel run={run} isRunning={isRunning} workingLabel={workingLabel} />;
  }
}
