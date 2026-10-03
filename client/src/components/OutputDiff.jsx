import { motion } from "motion/react"

import { cn } from "@/lib/cn"
import { diffOutputs } from "@/lib/diff"
import { ease } from "@/lib/motion"

import { ProvenanceTag } from "./ProvenanceTag"

/**
 * What the learner wrote next to what Python printed. Lines that differ are
 * underlined on the learner's side (the underline sweeps in) and marked on
 * the real side.
 */
export function OutputDiff({ student, real, studentLabel = "You wrote", realLabel = "The program printed" }) {
  const diff = diffOutputs(student, real)
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <OutputColumn label={studentLabel} lines={diff.student} tone="student" />
      <OutputColumn label={realLabel} lines={diff.real} tone="real" tag={<ProvenanceTag kind="exec" />} />
    </div>
  )
}

function OutputColumn({ label, lines, tone, tag }) {
  return (
    <div className="min-w-0 space-y-2">
      <div className="flex h-7 items-center justify-between gap-2">
        <span className="text-small font-medium text-muted">{label}</span>
        {tag}
      </div>
      <pre
        className={cn(
          "min-h-[3.5rem] overflow-x-auto rounded-panel border px-4 py-3 font-mono text-code",
          tone === "student" ? "border-rule-strong bg-surface" : "border-exec/25 bg-exec-soft/40",
        )}
      >
        {lines.length === 0 ? (
          <span className="font-sans text-small italic text-muted">prints nothing</span>
        ) : (
          lines.map((line, index) => (
            <div key={index} className="relative w-max min-w-full">
              {tone === "real" && line.differs && (
                <span aria-hidden="true" className="absolute -left-4 top-0 bottom-0 w-[3px] bg-exec" />
              )}
              <span className="relative inline-block whitespace-pre">
                {line.text || " "}
                {tone === "student" && line.differs && (
                  <motion.span
                    aria-hidden="true"
                    className="absolute -bottom-0.5 left-0 h-[2.5px] w-full origin-left rounded-full bg-active"
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ duration: 0.45, delay: 0.25 + index * 0.08, ease }}
                  />
                )}
              </span>
            </div>
          ))
        )}
      </pre>
    </div>
  )
}
