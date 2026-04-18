type TargetSidebarProps = {
  displayName: string;
  url: string;
};

export function TargetSidebar({ displayName, url }: TargetSidebarProps) {
  return (
    <section className="rounded-lg border border-border bg-surface-elevated p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-subtle">Target</h2>
      <p className="mt-2 text-base font-medium text-fg">{displayName || "—"}</p>
      {url ? (
        <a
          href={url.startsWith("http") ? url : `https://${url}`}
          target="_blank"
          rel="noreferrer"
          className="mt-1 block truncate text-sm text-link underline-offset-2 hover:underline"
        >
          {url}
        </a>
      ) : (
        <p className="mt-1 text-sm text-muted">No URL</p>
      )}
    </section>
  );
}
