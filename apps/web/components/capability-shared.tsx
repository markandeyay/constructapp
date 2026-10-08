"use client";

import { useState, type ReactNode } from "react";

// Small pieces shared by the AAV, assembly and guide RNA result panels. They use
// the same surface, border, caption and button classes as the plasmid map view.

export function PanelShell({
  id,
  title,
  subtitle,
  badge,
  children
}: {
  id: string;
  title: string;
  subtitle?: string;
  badge?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="flex min-h-full flex-col rounded-md border border-line bg-paper p-md shadow-raised" aria-labelledby={`${id}-title`}>
      <div className="flex items-start justify-between gap-md">
        <div>
          <h2 id={`${id}-title`} className="font-serif text-h3 text-ink">{title}</h2>
          {subtitle ? <p className="mt-2xs text-caption uppercase tracking-[0.06em] text-slate">{subtitle}</p> : null}
        </div>
        {badge}
      </div>
      {children}
    </section>
  );
}

export function EmptyPanel({ id, title, heading, text }: { id: string; title: string; heading: string; text: string }) {
  return (
    <section id={id} className="flex h-full min-h-0 flex-col rounded-md border border-line bg-paper p-md shadow-raised" aria-labelledby={`${id}-title-empty`}>
      <h2 id={`${id}-title-empty`} className="font-serif text-h3 text-ink">{title}</h2>
      <div className="mt-md flex h-full min-h-0 flex-1 flex-col items-center justify-center gap-sm rounded-md border border-dashed border-line-strong bg-mist px-lg text-center">
        <p className="font-serif text-h3 text-ink">{heading}</p>
        <p className="text-small leading-5 text-slate">{text}</p>
      </div>
    </section>
  );
}

export function Card({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`mt-md rounded-md border border-line bg-paper ${className}`} aria-label={title}>
      <div className="border-b border-line bg-mist px-md py-sm">
        <h3 className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">{title}</h3>
      </div>
      <div className="p-md">{children}</div>
    </section>
  );
}

export const SECONDARY_BUTTON =
  "rounded-md border border-line-strong bg-paper px-sm py-2xs text-sm font-semibold text-ink hover:bg-mist focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40 disabled:cursor-not-allowed disabled:text-slate";

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<"idle" | "copied" | "error">("idle");
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("error");
    }
    window.setTimeout(() => setState("idle"), 2500);
  }
  return (
    <span className="inline-flex items-center gap-xs">
      <button type="button" onClick={() => void copy()} className={SECONDARY_BUTTON}>
        {label}
      </button>
      <span className="text-caption text-slate" role="status" aria-live="polite">
        {state === "copied" ? "Copied" : state === "error" ? "Copy failed. Select the table and copy it manually." : ""}
      </span>
    </span>
  );
}

export function downloadText(filename: string, content: string, mime = "text/plain") {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "none";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

/**
 * The thresholds and settings a verdict was measured against (section 5.4 rule 3).
 * Rendered from the payload, never from constants in the UI.
 */
export function ParametersUsed({ parameters }: { parameters: Record<string, unknown> }) {
  const entries = Object.entries(parameters);
  if (!entries.length) {
    return null;
  }
  return (
    <details className="mt-md rounded-md border border-line bg-paper" data-testid="parameters-used">
      <summary className="cursor-pointer border-b border-transparent bg-mist px-md py-sm text-caption font-semibold uppercase tracking-[0.06em] text-slate focus:outline-none focus:ring-2 focus:ring-coral/40">
        Parameters used ({entries.length})
      </summary>
      <dl className="grid gap-x-md gap-y-2xs p-md text-xs sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
        {entries.map(([key, value]) => (
          <div key={key} className="contents">
            <dt className="font-semibold text-ink">{key}</dt>
            <dd className="break-words text-slate">{renderValue(value)}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
