import { motion } from "motion/react"

import { cn } from "@/lib/cn"
import { rise } from "@/lib/motion"

/** An inline explanation of what the system decided and why. */
export function Notice({ title, children, tone = "neutral", icon, className }) {
  return (
    <motion.div
      variants={rise}
      initial="hidden"
      animate="shown"
      className={cn(
        "flex gap-3 rounded-panel border px-4 py-3",
        tone === "neutral" && "border-rule bg-surface-2/60",
        tone === "warn" && "border-improving/30 bg-improving-soft",
        tone === "error" && "border-active/30 bg-active-soft",
        tone === "dashed" && "border-dashed border-rule-strong bg-transparent",
        className,
      )}
    >
      {icon && <span className="mt-0.5 shrink-0 text-ink-2">{icon}</span>}
      <div className="space-y-0.5">
        {title && <p className="text-[15px] font-semibold text-ink">{title}</p>}
        <div className="text-[15px] leading-relaxed text-ink-2">{children}</div>
      </div>
    </motion.div>
  )
}

/** A request failed; say what happened and offer the retry. */
export function ErrorNote({ error, onRetry, className }) {
  if (!error) return null
  return (
    <Notice tone="error" title="That didn't go through" className={className}>
      <span>{error.message ?? String(error)}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="ml-2 font-semibold text-active underline underline-offset-4">
          Try again
        </button>
      )}
    </Notice>
  )
}
