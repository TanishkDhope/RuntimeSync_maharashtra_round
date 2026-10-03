import { cn } from "@/lib/cn"

/** A quiet label: topic, confusable group, transfer type. */
export function Tag({ children, tone = "neutral", mono = false, className }) {
  return (
    <span
      className={cn(
        "inline-flex h-7 items-center whitespace-nowrap rounded-full px-2.5 text-small leading-none",
        tone === "neutral" && "bg-surface-2 text-ink-2",
        tone === "outline" && "border border-rule-strong text-ink-2",
        tone === "accent" && "bg-accent-soft text-accent",
        mono && "font-mono text-[13.5px]",
        className,
      )}
    >
      {children}
    </span>
  )
}
