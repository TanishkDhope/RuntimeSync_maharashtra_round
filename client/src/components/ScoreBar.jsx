import { motion } from "motion/react"

import { cn } from "@/lib/cn"
import { ease } from "@/lib/motion"

/** A horizontal bar that grows to `value / max` once mounted. */
export function ScoreBar({ value, max = 1, delay = 0, tone = "accent", className }) {
  const fraction = Math.max(0, Math.min(1, max > 0 ? value / max : 0))
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-surface-2", className)}>
      <motion.div
        className={cn(
          "h-full origin-left rounded-full",
          tone === "accent" && "bg-accent",
          tone === "muted" && "bg-muted/45",
          tone === "exec" && "bg-exec",
          tone === "hazard" && "bg-hazard",
        )}
        initial={{ scaleX: 0 }}
        animate={{ scaleX: fraction }}
        transition={{ duration: 0.7, delay, ease }}
      />
    </div>
  )
}
