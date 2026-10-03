import { ChevronDown } from "lucide-react"
import { AnimatePresence, motion } from "motion/react"
import { useId, useState } from "react"

import { cn } from "@/lib/cn"
import { ease, rise } from "@/lib/motion"

/**
 * One phase of a case in the thread. When the case moves on it folds into a
 * single summary line; the learner (or a judge) can open it again.
 *
 *   folded   - the thread's suggestion; a click overrides it until it changes
 *   summary  - the one-line text shown while folded
 *   tone     - "dashed" marks generated content (unknown draft etc.)
 */
export function Section({ index, phase, title, provenance, folded = false, summary, status, children, tone, className }) {
  const bodyId = useId()
  const [suggested, setSuggested] = useState(folded)
  const [override, setOverride] = useState(null)
  // Reset the learner's choice whenever the thread folds or unfolds this section.
  if (suggested !== folded) {
    setSuggested(folded)
    setOverride(null)
  }
  const open = override ?? !folded

  return (
    <motion.section
      layout="position"
      variants={rise}
      initial="hidden"
      animate="shown"
      className={cn(
        "rounded-panel border bg-surface",
        tone === "dashed" ? "border-dashed border-rule-strong" : "border-rule",
        className,
      )}
      aria-labelledby={`${bodyId}-title`}
    >
      <button
        type="button"
        onClick={() => setOverride(!open)}
        aria-expanded={open}
        aria-controls={bodyId}
        className="group flex w-full items-center gap-4 rounded-panel px-6 py-4 text-left"
      >
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="eyebrow flex items-center gap-2">
            {status}
            <span className="tabular">{String(index).padStart(2, "0")}</span>
            <span aria-hidden="true">·</span>
            <span>{phase}</span>
          </span>
          <AnimatePresence initial={false} mode="popLayout">
            {open ? (
              <motion.span
                key="title"
                id={`${bodyId}-title`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="font-serif text-h3 font-semibold text-ink"
              >
                {title}
              </motion.span>
            ) : (
              <motion.span
                key="summary"
                id={`${bodyId}-title`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="truncate text-[15px] text-ink-2"
              >
                {summary ?? title}
              </motion.span>
            )}
          </AnimatePresence>
        </span>
        {provenance && <span className="hidden shrink-0 items-center gap-2 sm:flex">{provenance}</span>}
        <ChevronDown
          aria-hidden="true"
          strokeWidth={1.5}
          className={cn(
            "size-5 shrink-0 text-muted transition-transform duration-200 group-hover:text-ink",
            open && "rotate-180",
          )}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={bodyId}
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease }}
            className="overflow-hidden"
          >
            <div className="space-y-6 border-t border-rule px-6 pb-6 pt-5">
              {provenance && <div className="flex flex-wrap gap-2 sm:hidden">{provenance}</div>}
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  )
}
