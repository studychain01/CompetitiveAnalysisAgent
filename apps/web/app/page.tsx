const defaultApi = "http://localhost:8000";

export default function Home() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? defaultApi;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 px-6 py-16 font-sans text-zinc-900 dark:bg-black dark:text-zinc-50">
      <main className="w-full max-w-xl space-y-6 rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-wide text-zinc-500">
            BattleScope monorepo
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">Web + API scaffold</h1>
          <p className="text-sm leading-6 text-zinc-600 dark:text-zinc-400">
            Next.js lives in <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs dark:bg-zinc-900">apps/web</code>
            . Python FastAPI + LangGraph lives in{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs dark:bg-zinc-900">apps/api</code>.
          </p>
        </div>
        <div className="space-y-3 text-sm">
          <p className="font-medium text-zinc-800 dark:text-zinc-200">API base URL</p>
          <code className="block rounded-lg bg-zinc-100 px-3 py-2 text-xs text-zinc-800 dark:bg-zinc-900 dark:text-zinc-100">
            {apiBase}
          </code>
          <a
            className="inline-flex text-sm font-medium text-blue-600 underline-offset-4 hover:underline dark:text-blue-400"
            href={`${apiBase}/health`}
            target="_blank"
            rel="noreferrer"
          >
            Open /health
          </a>
        </div>
      </main>
    </div>
  );
}
