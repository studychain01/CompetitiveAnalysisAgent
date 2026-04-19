"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getApiBase, startStreamRun } from "@/lib/api";
import { getFirstUnlockedTab, getTabUiState, type TabId } from "@/lib/tab-stage";
import type { RunSseMessage, RunStreamStartResponse, RunSyncResponse } from "@/lib/types";

import { AppShell } from "./AppShell";
import { RunForm } from "./RunForm";
import { RunHeader } from "./RunHeader";

function emptyRunFromMeta(meta: RunStreamStartResponse): RunSyncResponse {
  return {
    run_id: meta.run_id,
    thread_id: meta.thread_id,
    stage: "",
    company_profile: {},
    company_url_normalized: null,
    planner_notes: [],
    trace_events: [],
    sec_risk_dossier: {},
    competitor_landscape: {},
    peer_research_digests: {},
    competitive_strategy: {},
  };
}

function mergeStreamPayload(prev: RunSyncResponse, payload: Record<string, unknown>): RunSyncResponse {
  const asObj = (v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {});
  const asList = <T,>(v: unknown, fallback: T[]): T[] => (Array.isArray(v) ? (v as T[]) : fallback);

  return {
    run_id: prev.run_id,
    thread_id: prev.thread_id,
    stage: typeof payload.stage === "string" ? payload.stage : prev.stage,
    company_profile: (asObj(payload.company_profile) || prev.company_profile) as RunSyncResponse["company_profile"],
    company_url_normalized:
      payload.company_url_normalized !== undefined
        ? (payload.company_url_normalized as string | null)
        : prev.company_url_normalized,
    planner_notes: asList<string>(payload.planner_notes, prev.planner_notes),
    trace_events: asList<RunSyncResponse["trace_events"][number]>(payload.trace_events, prev.trace_events),
    sec_risk_dossier: (asObj(payload.sec_risk_dossier) || prev.sec_risk_dossier) as RunSyncResponse["sec_risk_dossier"],
    competitor_landscape: (asObj(payload.competitor_landscape) ||
      prev.competitor_landscape) as RunSyncResponse["competitor_landscape"],
    peer_research_digests: (asObj(payload.peer_research_digests) ||
      prev.peer_research_digests) as RunSyncResponse["peer_research_digests"],
    competitive_strategy: (asObj(payload.competitive_strategy) ||
      prev.competitive_strategy) as RunSyncResponse["competitive_strategy"],
  };
}

export function RunDashboard() {
  const esRef = useRef<EventSource | null>(null);
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

  useEffect(() => {
    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!run) return;
    const ctx = { stage: run.stage || "", isRunning: loading, run };
    if (getTabUiState(activeTab as TabId, ctx) === "locked") {
      setActiveTab(getFirstUnlockedTab(ctx));
    }
  }, [run, loading, activeTab]);

  const onNewRun = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setRun(null);
    setError(null);
    setActiveTab("overview");
    setRunStartedAt(null);
    setFreezeAt(null);
    setElapsedSeconds(0);
    setLoading(false);
  }, []);

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setLoading(true);
      setFreezeAt(null);
      setRunStartedAt(Date.now());
      esRef.current?.close();
      esRef.current = null;

      try {
        const meta = await startStreamRun({
          company_name: companyName,
          company_url: companyUrl,
        });
        setRun(emptyRunFromMeta(meta));

        const url = `${getApiBase()}${meta.events_url}`;
        const es = new EventSource(url);
        esRef.current = es;

        es.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data) as RunSseMessage;
            if (msg.type === "error") {
              const detail = (msg.payload as { detail?: string }).detail ?? "Stream error";
              setError(detail);
              es.close();
              esRef.current = null;
              setLoading(false);
              setFreezeAt(Date.now());
              return;
            }
            if (msg.type === "state" || msg.type === "complete") {
              setRun((prev) => (prev ? mergeStreamPayload(prev, msg.payload) : prev));
            }
            if (msg.type === "complete") {
              es.close();
              esRef.current = null;
              setLoading(false);
              setFreezeAt(Date.now());
            }
          } catch {
            setError("Invalid server event");
            es.close();
            esRef.current = null;
            setLoading(false);
            setFreezeAt(Date.now());
          }
        };

        es.onerror = () => {
          if (es.readyState === EventSource.CLOSED) return;
          setError((prev) => prev ?? "EventSource connection error");
          es.close();
          esRef.current = null;
          setLoading(false);
          setFreezeAt(Date.now());
        };
      } catch (err) {
        setRun(null);
        setFreezeAt(Date.now());
        setError(err instanceof Error ? err.message : "Request failed");
        setLoading(false);
      }
    },
    [companyName, companyUrl],
  );

  return (
    <div className="flex h-screen min-h-0 flex-col bg-canvas text-fg">
      <RunHeader
        runId={run?.run_id ?? null}
        elapsedSeconds={elapsedSeconds}
        live={loading}
        pipelineStage={run?.stage ?? ""}
      />
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
          isRunning={loading}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onNewRun={onNewRun}
        />
      )}
    </div>
  );
}
