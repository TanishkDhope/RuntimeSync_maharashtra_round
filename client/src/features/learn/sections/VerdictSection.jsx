import { ArrowRight } from "lucide-react"
import { motion } from "motion/react"
import { useEffect, useState } from "react"

import { Section } from "@/components/Section"
import { StatusChip } from "@/components/StatusChip"
import { cn } from "@/lib/cn"
import { ease, rise, stagger } from "@/lib/motion"

import { Belief, PhaseMark } from "../parts"

const STAMP = {
  resolved: { word: "Resolved", className: "border-exec text-exec" },
  improving: { word: "Improving", className: "border-improving text-improving" },
  active: { word: "Still active", className: "border-active text-active" },
}

/** 06 · Verdict: resolved / improving / still active, and exactly why. */
export function VerdictSection({ c, folded }) {
  const { verdict, reasons, record } = c.verdict
  const stamp = STAMP[verdict]

  return (
    <Section
      index={6}
      phase="Verdict"
      status={<PhaseMark state="done" />}
      title="The verdict"
      summary={`${stamp.word} · ${record.misconception_id}`}
      folded={folded}
    >
      <div className="grid items-start gap-8 md:grid-cols-[auto_minmax(0,1fr)]">
        <motion.div
          initial={{ opacity: 0, scale: 1.08, rotate: -6 }}
          animate={{ opacity: 1, scale: 1, rotate: -2 }}
          transition={{ duration: 0.5, ease }}
          className={cn(
            "inline-flex flex-col items-center rounded-panel border-[3px] px-6 py-4 font-serif",
            stamp.className,
          )}
        >
          <span className="text-[34px] font-semibold leading-none">{stamp.word}</span>
          <span className="mt-1.5 font-sans text-[12px] font-semibold uppercase tracking-[0.14em] opacity-80">
            {record.misconception_id}
          </span>
        </motion.div>

        <motion.ul variants={stagger(0.1, 0.35)} initial="hidden" animate="shown" className="space-y-2.5">
          {reasons.map((reason, i) => (
            <motion.li key={i} variants={rise} className="flex gap-3 text-[16px] leading-snug">
              <span
                aria-label={reason.ok ? "met" : "not met"}
                className={cn(
                  "mt-0.5 grid size-5 shrink-0 place-items-center rounded-full text-[12px] font-bold",
                  reason.ok ? "bg-exec-soft text-exec" : "bg-active-soft text-active",
                )}
              >
                {reason.ok ? "✓" : "✗"}
              </span>
              <span className="text-ink-2">{reason.text}</span>
            </motion.li>
          ))}
        </motion.ul>
      </div>

      <RecordChange record={record} />
    </Section>
  )
}

/** The learner record line; the chip morphs from the old status to the new one. */
function RecordChange({ record }) {
  const [shown, setShown] = useState(record.from ?? null)
  useEffect(() => {
    const timer = setTimeout(() => setShown(record.to), 900)
    return () => clearTimeout(timer)
  }, [record.to])

  return (
    <motion.div
      variants={rise}
      initial="hidden"
      animate="shown"
      className="space-y-3 rounded-panel border border-rule bg-surface-2/40 px-5 py-4"
    >
      <span className="eyebrow">Learner record updated</span>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <Belief className="min-w-0 flex-1 text-[17px]">{record.description}</Belief>
        <div className="flex items-center gap-2.5">
          <span className="text-small text-muted">{record.from ? `was ${record.from}` : "first time seen"}</span>
          <ArrowRight className="size-4 text-muted" strokeWidth={1.75} />
          <StatusChip status={shown ?? record.to} />
        </div>
      </div>
    </motion.div>
  )
}
