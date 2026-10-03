import { ArrowRight } from "lucide-react"
import { motion } from "motion/react"

import { Button } from "@/components/Button"
import { ErrorNote } from "@/components/Notice"
import { cn } from "@/lib/cn"
import { rise } from "@/lib/motion"

/** A belief, set as a quoted human thought. */
export function Belief({ children, size = "md", className }) {
  return (
    <p
      className={cn(
        "font-serif text-ink",
        size === "lg" ? "text-belief" : "text-[19px] leading-snug",
        className,
      )}
    >
      “{children}”
    </p>
  )
}

/** The learner's one-line reason, quoted. */
export function ReasonQuote({ children }) {
  return (
    <div className="space-y-1.5">
      <span className="text-small font-medium text-muted">Your reason</span>
      <blockquote className="border-l-[3px] border-rule-strong pl-4 font-serif text-[18px] italic leading-snug text-ink-2">
        {children}
      </blockquote>
    </div>
  )
}

/** Small status glyph for section eyebrows. */
export function PhaseMark({ state }) {
  if (state === "done") return <span className="text-exec" aria-label="done">✓</span>
  if (state === "skipped") return <span className="text-muted" aria-label="skipped">–</span>
  return <span className="text-accent" aria-label="in progress">◉</span>
}

/** The single "continue" action under the step on screen. */
export function ContinueBar({ label, onContinue, busy, busyLabel, error, note }) {
  return (
    <motion.div variants={rise} initial="hidden" animate="shown" className="space-y-3 pt-2">
      <ErrorNote error={error} onRetry={onContinue} />
      <div className="flex flex-wrap items-center gap-4">
        <Button
          size="lg"
          onClick={onContinue}
          loading={busy}
          autoFocus
          icon={<ArrowRight className="size-[18px]" strokeWidth={1.75} />}
        >
          {busy ? busyLabel : label}
        </Button>
        {note && <span className="text-small text-muted">{note}</span>}
      </div>
    </motion.div>
  )
}
