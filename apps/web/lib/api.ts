import type { CreateRunBody, RunStreamStartResponse, RunSyncResponse } from "./types";

const defaultApi = "http://localhost:8000";

export function getApiBase(): string {
  const base = process.env.NEXT_PUBLIC_API_URL ?? defaultApi;
  return base.replace(/\/$/, "");
}

export async function startStreamRun(body: CreateRunBody): Promise<RunStreamStartResponse> {
  const res = await fetch(`${getApiBase()}/runs/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_name: body.company_name?.trim() || null,
      company_url: body.company_url?.trim() || null,
    }),
  });
  if (res.status !== 202) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<RunStreamStartResponse>;
}

export async function createRun(body: CreateRunBody): Promise<RunSyncResponse> {
  const res = await fetch(`${getApiBase()}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_name: body.company_name?.trim() || null,
      company_url: body.company_url?.trim() || null,
    }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<RunSyncResponse>;
}
