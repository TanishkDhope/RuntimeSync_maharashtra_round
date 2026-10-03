import { motion } from "motion/react"

import { cn } from "@/lib/cn"
import { rise } from "@/lib/motion"

/** Says plainly that something isn't there yet. Never filled with placeholder numbers. */
export function EmptyState({ eyebrow, title, children, action, className }) {
  return (
    <motion.div
      variants={rise}
      initial="hidden"
      animate="shown"
      className={cn(
        "mx-auto flex max-w-xl flex-col items-start gap-4 rounded-panel border border-dashed border-rule-strong px-8 py-10",
        className,
      )}
    >
      {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      <h2 className="font-serif text-h2 font-semibold text-ink">{title}</h2>
      <div className="space-y-2 text-body text-ink-2">{children}</div>
      {action}
    </motion.div>
  )
}
