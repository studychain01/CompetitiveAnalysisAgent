"use client";

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
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md space-y-5 rounded-2xl border border-border bg-surface-elevated p-8 shadow-lg"
      >
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-fg">New research run</h1>
          <p className="mt-1 text-sm text-muted">Calls the BattleScope graph (blocking until complete).</p>
        </div>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-subtle">Company name</span>
          <input
            value={companyName}
            onChange={(e) => onNameChange(e.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-fg outline-none ring-accent focus:border-accent focus:ring-1"
            placeholder="e.g. Linear"
            disabled={loading}
            autoComplete="organization"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-subtle">Company URL</span>
          <input
            value={companyUrl}
            onChange={(e) => onUrlChange(e.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-sm text-fg outline-none ring-accent focus:border-accent focus:ring-1"
            placeholder="https://linear.app"
            disabled={loading}
            autoComplete="url"
          />
        </label>
        {error ? (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-fg" role="alert">
            {error}
          </div>
        ) : null}
        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-canvas transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-canvas border-t-transparent" />
              Running graph…
            </>
          ) : (
            "Run analysis"
          )}
        </button>
      </form>
    </div>
  );
}
