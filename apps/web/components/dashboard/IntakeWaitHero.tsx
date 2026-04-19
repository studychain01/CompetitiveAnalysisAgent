"use client";

import { useEffect, useState } from "react";

const TIPS = [
  "Pulling together filings, news, and the open web.",
  "First results usually land within a minute.",
  "You will see the overview as soon as the profile step completes.",
  "Deep dive and strategy tabs unlock as each stage finishes.",
] as const;

type Props = {
  /** Company name from the form while the profile artifact is still empty */
  workingLabel: string;
};

export function IntakeWaitHero({ workingLabel }: Props) {
  const [tipIndex, setTipIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setTipIndex((i) => (i + 1) % TIPS.length);
    }, 4500);
    return () => clearInterval(id);
  }, []);

  const label = workingLabel.trim() || "your company";

  return (
    <div className="relative mx-auto flex min-h-[min(70vh,520px)] max-w-lg flex-col items-center justify-center px-4 py-16">
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.35]"
        aria-hidden
      >
        <div className="absolute left-1/2 top-1/2 h-[min(90vw,420px)] w-[min(90vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/20 blur-3xl animate-pulse" />
        <div
          className="absolute left-1/2 top-1/2 h-[min(70vw,320px)] w-[min(70vw,320px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-link/15 blur-2xl animate-pulse"
          style={{ animationDelay: "0.6s" }}
        />
      </div>

      <div
        className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-accent/20 bg-surface/80 shadow-lg backdrop-blur-sm"
        aria-hidden
      >
        <span className="absolute inset-2 rounded-xl border-2 border-accent/30 border-t-accent animate-spin" />
        <span className="text-2xl font-semibold tracking-tight text-accent/90">B</span>
      </div>

      <h1 className="mt-10 text-center text-xl font-semibold tracking-tight text-fg sm:text-2xl">
        Preparing intelligence for{" "}
        <span className="bg-gradient-to-r from-accent to-link bg-clip-text text-transparent">{label}</span>
      </h1>

      <p className="mt-3 text-center text-sm leading-relaxed text-muted">
        The overview will appear here as soon as we have a grounded company profile.
      </p>

      <div className="mt-10 min-h-[3rem] w-full max-w-md text-center">
        <p key={tipIndex} className="animate-tip-fade text-sm leading-relaxed text-subtle">
          {TIPS[tipIndex]}
        </p>
      </div>

      <div className="mt-12 flex w-full max-w-md flex-col gap-2 rounded-xl border border-border/80 bg-surface-elevated/50 px-4 py-3 text-left text-xs text-muted">
        <p className="font-semibold uppercase tracking-wider text-subtle">What is running</p>
        <p>Intake agents are searching public sources and normalizing what they find into your dashboard.</p>
      </div>
    </div>
  );
}
