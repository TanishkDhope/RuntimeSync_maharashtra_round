import { motion } from "motion/react"
import { useId, useMemo } from "react"

import { cn } from "@/lib/cn"
import { highlightLines } from "@/lib/highlight"
import { spring } from "@/lib/motion"

/**
 * Read-only Python, always on the dark panel so code is the sharpest thing on
 * a projector.
 *   activeLine - the line about to run (trace); the highlight glides between lines
 *   markLine   - where the learner's belief parts ways with Python (highlighter)
 *   note       - a margin note shown under markLine
 *   running    - an indeterminate hairline while the code is being checked
 */
export function CodeBlock({ code, activeLine = null, markLine = null, note = null, running = false, className, label }) {
  const lines = useMemo(() => highlightLines(code ?? ""), [code])
  const cursorId = useId()

  return (
    <figure
      className={cn(
        "code-surface relative overflow-hidden rounded-panel border border-code-rule bg-code-bg",
        className,
      )}
    >
      {label && (
        <figcaption className="flex h-9 items-center border-b border-code-rule px-4 font-mono text-[13px] tracking-wide text-code-muted">
          {label}
        </figcaption>
      )}
      {running && (
        <div className="absolute inset-x-0 top-0 h-0.5 overflow-hidden" aria-hidden="true">
          <div className="hairline-run h-full w-2/5 bg-accent" />
        </div>
      )}
      <pre className="overflow-x-auto py-3 text-code">
        <code className="block min-w-max">
          {lines.map((tokens, index) => {
            const number = index + 1
            const active = number === activeLine
            const marked = number === markLine
            return (
              <div key={number}>
                <div className="relative grid grid-cols-[3.25rem_1fr]">
                  {marked && (
                    <span
                      aria-hidden="true"
                      className="absolute inset-y-0 left-0 right-0 border-l-[3px] border-[#ffd65a] bg-[#ffd65a]/14"
                    />
                  )}
                  {active && (
                    <motion.span
                      layoutId={cursorId}
                      transition={spring}
                      aria-hidden="true"
                      className="absolute inset-0 border-l-[3px] border-accent bg-white/[0.07]"
                    />
                  )}
                  <span
                    className={cn(
                      "relative select-none pr-4 text-right tabular",
                      active ? "text-code-ink" : "text-code-muted",
                    )}
                  >
                    {number}
                  </span>
                  <span className="relative whitespace-pre pr-6">
                    {tokens.length === 0
                      ? " "
                      : tokens.map((token, i) => (
                          <span key={i} className={token.cls || undefined}>
                            {token.text}
                          </span>
                        ))}
                  </span>
                </div>
                {marked && note && (
                  <div className="relative grid grid-cols-[3.25rem_1fr] pb-1">
                    <span />
                    <span className="mr-6 mt-1 border-l-[3px] border-[#ffd65a] pl-3 font-serif text-[16px] italic leading-snug text-[#f3dd94]">
                      {note}
                    </span>
                  </div>
                )}
              </div>
            )
          })}
        </code>
      </pre>
    </figure>
  )
}
