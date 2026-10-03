import { AnimatePresence, motion } from "motion/react"

import { cn } from "@/lib/cn"
import { base } from "@/lib/motion"

const STATUS = {
  active: { label: "Still active", className: "bg-active-soft text-active", glyph: "●" },
  improving: { label: "Improving", className: "bg-improving-soft text-improving", glyph: "◐" },
  resolved: { label: "Resolved", className: "bg-exec-soft text-exec", glyph: "✓" },
}

/** Learner status for one belief. Colour is never the only signal: glyph + word. */
export function StatusChip({ status, className, size = "md" }) {
  const spec = STATUS[status] ?? { label: "New", className: "bg-surface-2 text-muted", glyph: "○" }
  return (
    <motion.span
      layout
      transition={base}
      className={cn(
        "inline-flex items-center gap-1.5 overflow-hidden whitespace-nowrap rounded-full font-medium leading-none",
        size === "md" ? "h-7 px-2.5 text-small" : "h-9 px-3.5 text-body",
        spec.className,
        className,
      )}
    >
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={status ?? "new"}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={base}
          className="inline-flex items-center gap-1.5"
        >
          <span aria-hidden="true">{spec.glyph}</span>
          {spec.label}
        </motion.span>
      </AnimatePresence>
    </motion.span>
  )
}
