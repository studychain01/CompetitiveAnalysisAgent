"use client";

import { useCallback, useEffect, useState } from "react";

import { createRun } from "@/lib/api";
import type { RunSyncResponse } from "@/lib/types";

import { AppShell } from "./AppShell";
import { RunForm } from "./RunForm";
import { RunHeader } from "./RunHeader";

export function RunDashboard() {
  const [companyName, setCompanyName] = useState("");
  const [companyUrl, setCompanyUrl] = useState("");
  const [run, setRun] = useState<RunSyncResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [freezeAt, setFreezeAt] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (runStartedAt === null) return;
    const tick = () => {
      const end = freezeAt ?? Date.now();
      setElapsedSeconds(Math.floor((end - runStartedAt) / 1000));
    };
    tick();
    if (freezeAt !== null) return;
    const id = setInterval(tick, 500);
    return () => clearInterval(id);
  }, [runStartedAt, freezeAt]);

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setLoading(true);
      setFreezeAt(null);
      setRunStartedAt(Date.now());
      try {
        const result = await createRun({
          company_name: companyName,
          company_url: companyUrl,
        });
        setRun(result);
        setFreezeAt(Date.now());
      } catch (err) {
        setRun(null);
        setFreezeAt(Date.now());
        setError(err instanceof Error ? err.message : "Request failed");
      } finally {
        setLoading(false);
      }
    },
    [companyName, companyUrl],
  );

  const onNewRun = useCallback(() => {
    setRun(null);
    setError(null);
    setActiveTab("overview");
    setRunStartedAt(null);
    setFreezeAt(null);
    setElapsedSeconds(0);
  }, []);

  return (
    <div className="flex h-screen min-h-0 flex-col bg-canvas text-fg">
      <RunHeader runId={run?.run_id ?? null} elapsedSeconds={elapsedSeconds} live={loading} />
      {!run ? (
        <RunForm
          companyName={companyName}
          companyUrl={companyUrl}
          onNameChange={setCompanyName}
          onUrlChange={setCompanyUrl}
          onSubmit={onSubmit}
          loading={loading}
          error={error}
        />
      ) : (
        <AppShell
          run={run}
          submittedName={companyName}
          submittedUrl={companyUrl}
          isRunning={false}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onNewRun={onNewRun}
        />
      )}
    </div>
  );
}
