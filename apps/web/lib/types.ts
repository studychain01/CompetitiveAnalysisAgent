/**
 * Mirrors FastAPI RunSyncResponse and nested graph payloads (loose where backend is dict-shaped).
 */

export type TraceEvent = {
  event_type: string;
  run_id: string;
  message: string;
  payload?: Record<string, unknown>;
};

export type RunSyncResponse = {
  run_id: string;
  thread_id: string;
  stage: string;
  company_profile: Record<string, unknown>;
  company_url_normalized?: string | null;
  planner_notes: string[];
  trace_events: TraceEvent[];
  sec_risk_dossier: Record<string, unknown>;
  competitor_landscape: Record<string, unknown>;
  peer_research_digests: Record<string, unknown>;
  competitive_strategy: Record<string, unknown>;
};

export type CreateRunBody = {
  company_name?: string | null;
  company_url?: string | null;
};
