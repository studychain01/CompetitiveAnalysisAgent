"use client";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "risk", label: "Risk" },
  { id: "competitors", label: "Competitors" },
  { id: "peers", label: "Peers" },
  { id: "strategy", label: "Strategy" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

type TabNavProps = {
  active: string;
  onChange: (tab: string) => void;
};

export function TabNav({ active, onChange }: TabNavProps) {
  return (
    <nav className="flex flex-wrap gap-1" aria-label="Report sections">
      {TABS.map((tab) => {
        const isActive = active === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={
              isActive
                ? "rounded-md bg-accent-subtle px-3 py-1.5 text-sm font-medium text-accent"
                : "rounded-md px-3 py-1.5 text-sm font-medium text-muted transition hover:bg-surface-elevated hover:text-fg"
            }
          >
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}
