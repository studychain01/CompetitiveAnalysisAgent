"use client";

import { tabTooltip, type TabId, type TabUiState } from "@/lib/tab-stage";

export const TAB_IDS: TabId[] = ["overview", "risk", "competitors", "peers", "strategy"];

const TAB_LABELS: Record<TabId, string> = {
  overview: "Overview",
  risk: "Risk",
  competitors: "Competitors",
  peers: "Deep dives",
  strategy: "Strategy",
};

type TabNavProps = {
  active: string;
  tabStates: Record<TabId, TabUiState>;
  onChange: (tab: string) => void;
};

export function TabNav({ active, tabStates, onChange }: TabNavProps) {
  return (
    <nav className="flex flex-wrap gap-1" aria-label="Report sections">
      {TAB_IDS.map((tabId) => {
        const state = tabStates[tabId];
        const isActive = active === tabId;
        const disabled = state === "locked";
        const tooltip = tabTooltip(tabId, state);

        const base =
          "rounded-md px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-45";

        let cls = base;
        if (disabled) {
          cls += " text-subtle";
        } else if (state === "running") {
          cls += isActive
            ? " border-2 border-accent bg-accent-subtle text-accent shadow-sm ring-1 ring-accent/30"
            : " border border-accent/40 bg-accent-subtle/80 text-accent animate-pulse";
        } else if (isActive) {
          cls += " bg-accent text-white shadow-sm";
        } else {
          cls += " text-muted hover:bg-surface-elevated hover:text-fg";
        }

        return (
          <button
            key={tabId}
            type="button"
            disabled={disabled}
            title={tooltip}
            aria-disabled={disabled}
            onClick={() => {
              if (!disabled) onChange(tabId);
            }}
            className={cls}
          >
            {state === "running" ? `${TAB_LABELS[tabId]} · updating` : TAB_LABELS[tabId]}
          </button>
        );
      })}
    </nav>
  );
}

export type { TabId };
