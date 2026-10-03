import { cn } from "@/lib/cn"

/**
 * Where a piece of content came from. One consistent tag everywhere, because
 * judges will ask which results are ours and which are the LLM's.
 *   model    - our trained diagnosis model     (solid accent dot)
 *   stub     - the no-ML stand-in               (hazard)
 *   exec     - we really ran the code           (green play mark)
 *   llm      - generated text                   (hollow diamond, dashed)
 *   authored - written by the team              (neutral)
 *   bank     - taken from problems.jsonl        (outline)
 */
const KINDS = {
  model: {
    label: "Trained model",
    className: "border-accent/30 bg-accent-soft text-accent",
    glyph: <circle cx="5" cy="5" r="4" fill="currentColor" />,
  },
  stub: {
    label: "Stub diagnoser",
    className: "border-hazard/60 bg-hazard/25 text-hazard-ink dark:text-hazard",
    glyph: <path d="M5 1 9.2 9H.8Z" fill="currentColor" />,
  },
  exec: {
    label: "Ran the code",
    className: "border-exec/30 bg-exec-soft text-exec",
    glyph: <path d="M2 1.2v7.6L8.6 5Z" fill="currentColor" />,
  },
  llm: {
    label: "Generated",
    className: "border-dashed border-muted/70 bg-transparent text-ink-2",
    glyph: <path d="M5 1 9 5 5 9 1 5Z" fill="none" stroke="currentColor" strokeWidth="1.3" />,
  },
  authored: {
    label: "Written by the team",
    className: "border-rule-strong bg-surface-2 text-ink-2",
    glyph: <path d="M1.5 8.5h7M2 6.5l4.5-4.5 1.5 1.5L3.5 8" fill="none" stroke="currentColor" strokeWidth="1.2" />,
  },
  bank: {
    label: "Problem bank",
    className: "border-rule-strong bg-transparent text-ink-2",
    glyph: <rect x="1.5" y="1.5" width="7" height="7" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.3" />,
  },
}

export function ProvenanceTag({ kind, label, detail, className }) {
  const spec = KINDS[kind]
  return (
    <span
      title={detail}
      className={cn(
        "inline-flex h-7 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 text-small font-medium leading-none",
        spec.className,
        className,
      )}
    >
      <svg viewBox="0 0 10 10" className="size-2.5" aria-hidden="true">
        {spec.glyph}
      </svg>
      {label ?? spec.label}
    </span>
  )
}

/** The diagnoser that produced a ranking: trained model or stub. */
export function DiagnoserTag({ diagnosis, className }) {
  return diagnosis?.diagnoser_is_real_model ? (
    <ProvenanceTag kind="model" detail={`diagnoser: ${diagnosis.diagnoser}`} className={className} />
  ) : (
    <ProvenanceTag kind="stub" detail={`diagnoser: ${diagnosis?.diagnoser ?? "stub"}`} className={className} />
  )
}
