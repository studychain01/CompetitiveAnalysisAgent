"use client";

import { getApiBase } from "@/lib/api";

type RunFormProps = {
  companyName: string;
  companyUrl: string;
  onNameChange: (v: string) => void;
  onUrlChange: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
  error: string | null;
};

export function RunForm({
  companyName,
  companyUrl,
  onNameChange,
  onUrlChange,
  onSubmit,
  loading,
  error,
}: RunFormProps) {
  const apiBase = getApiBase();

  return (
    <div className="flex flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-6 py-10 lg:flex-row lg:items-stretch lg:gap-14 lg:py-14">
        <div className="flex max-w-xl flex-1 flex-col justify-center space-y-6">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-accent">BattleScope</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-fg sm:text-4xl">
              Live competitive intelligence
            </h1>
            <p className="mt-3 text-base leading-relaxed text-muted">
              Profile the company, pull SEC risk context, map competitors, run parallel deep dives on top rivals, and
              synthesize a prioritized strategy—streamed step by step as the agent works.
            </p>
          </div>
          <ul className="space-y-3 text-sm text-muted">
            <li className="flex gap-3">
              <span className="mt-0.5 font-semibold text-accent">1.</span>
              <span>Pipeline updates in real time so you are never staring at a blank screen.</span>
            </li>
            <li className="flex gap-3">
              <span className="mt-0.5 font-semibold text-accent">2.</span>
              <span>Tabs unlock as each stage completes—no empty placeholders.</span>
            </li>
            <li className="flex gap-3">
              <span className="mt-0.5 font-semibold text-accent">3.</span>
              <span>Evidence-backed outputs: competitors, peer digests, and a battle plan you can defend.</span>
            </li>
          </ul>
          <p className="text-sm text-subtle">
            <a
              href={`${apiBase}/health`}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-link underline-offset-2 hover:underline"
            >
              API health
            </a>
          </p>
          <details className="rounded-lg border border-border bg-surface-elevated p-3 text-xs text-muted">
            <summary className="cursor-pointer font-medium text-fg">For developers</summary>
            <p className="mt-2 font-mono leading-relaxed">
              POST <span className="text-accent">{apiBase}/runs/start</span> (202) then GET{" "}
              <span className="text-accent">/runs/{"{run_id}"}/events</span> (SSE).
            </p>
          </details>
        </div>

        <div className="flex flex-1 flex-col justify-center lg:max-w-md">
          <form
            onSubmit={onSubmit}
            className="space-y-5 rounded-2xl border border-border bg-surface p-8 shadow-md shadow-slate-900/5"
          >
            <div>
              <h2 className="text-lg font-semibold text-fg">Start a run</h2>
              <p className="mt-1 text-sm text-muted">Company name and site URL are enough to begin.</p>
            </div>
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-subtle">Company name</span>
              <input
                value={companyName}
                onChange={(e) => onNameChange(e.target.value)}
                className="w-full rounded-lg border border-border bg-canvas px-3 py-2.5 text-sm text-fg outline-none ring-accent/30 focus:border-accent focus:ring-2"
                placeholder="e.g. Boeing"
                disabled={loading}
                autoComplete="organization"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-subtle">Company website</span>
              <input
                value={companyUrl}
                onChange={(e) => onUrlChange(e.target.value)}
                className="w-full rounded-lg border border-border bg-canvas px-3 py-2.5 font-mono text-sm text-fg outline-none ring-accent/30 focus:border-accent focus:ring-2"
                placeholder="https://www.boeing.com"
                disabled={loading}
                autoComplete="url"
              />
              <span className="text-xs text-subtle">Include https:// when possible for best crawl results.</span>
            </label>
            {error ? (
              <div className="rounded-lg border border-danger/35 bg-danger/10 px-3 py-2 text-sm text-fg" role="alert">
                {error}
              </div>
            ) : null}
            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  Starting run…
                </>
              ) : (
                "Run analysis"
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
