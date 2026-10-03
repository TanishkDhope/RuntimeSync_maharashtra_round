import { ChevronDown } from "lucide-react"
import { AnimatePresence, motion } from "motion/react"
import { useState } from "react"

import { cn } from "@/lib/cn"
import { pad2 } from "@/lib/format"
import { ease } from "@/lib/motion"

import { busyLabel, caseProblem, continueLabel, focusPhase, takesAnswer } from "./caseModel"
import { ContinueBar } from "./parts"
import { AnswerSection } from "./sections/AnswerSection"
import { DiagnoseSection } from "./sections/DiagnoseSection"
import { ExplainSection } from "./sections/ExplainSection"
import { ProbeSection } from "./sections/ProbeSection"
import { RetestSection } from "./sections/RetestSection"
import { VerdictSection } from "./sections/VerdictSection"

/**
 * One case, phase by phase. The section on screen is open; the rest fold into
 * one-line summaries. `live` means this is the case being worked on now.
 */
export function CaseView({ c, live, thread }) {
  const focus = live ? focusPhase(c) : null
  const fold = (phase) => phase !== focus
  const form = live
    ? {
        onSubmit: (response, reason) => thread.answer.mutate({ response, reason }),
        busy: thread.answer.isPending,
        busyLabel: busyLabel(c, "answer"),
        error: thread.answer.error,
      }
    : null
  const last = c.last

  return (
    <div className="space-y-3">
      <AnswerSection
        c={c}
        folded={fold("answer")}
        interactive={live && last?.step === "ask" && last.phase !== "reassess"}
        form={form}
      />
      {c.graded && !c.correct && c.diagnosis && <DiagnoseSection c={c} folded={fold("diagnose")} />}
      {c.probe && (
        <ProbeSection c={c} folded={fold("probe")} interactive={live && last?.step === "probe"} form={{
          onSubmit: (response) => thread.probe.mutate(response), busy: thread.probe.isPending,
          busyLabel: "Checking your diagnostic response…", error: thread.probe.error,
        }} />
      )}
      {c.intervention && <ExplainSection c={c} folded={fold("explain")} />}
      {c.retest.items.length > 0 && (
        <RetestSection c={c} folded={fold("retest")} interactive={live} form={form} />
      )}
      {c.verdict && <VerdictSection c={c} folded={fold("verdict")} />}

      {live && !takesAnswer(c) && (
        <ContinueBar
          label={continueLabel(c)}
          onContinue={() => thread.advance.mutate()}
          busy={thread.advance.isPending}
          busyLabel={busyLabel(c, "next")}
          error={thread.advance.error}
          note={
            c.legacy && !c.correct && !c.probe
              ? "The backend doesn't serve the probe, explanation and retest steps yet."
              : undefined
          }
        />
      )}
    </div>
  )
}

/** A finished case, folded to one line until opened. */
export function PastCase({ c }) {
  const [open, setOpen] = useState(false)
  const problem = caseProblem(c)
  const outcome = c.verdict
    ? `${c.verdict.verdict} · ${c.verdict.record.misconception_id}`
    : c.correct
      ? "correct"
      : c.unknown
        ? "no library match"
        : c.diagnosis?.candidates?.[0]
          ? c.diagnosis.candidates[0].misconception_id
          : "wrong"

  return (
    <div className="rounded-panel border border-rule bg-surface/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-4 px-6 py-3 text-left"
      >
        <span
          className={cn(
            "grid size-6 shrink-0 place-items-center rounded-full text-[12px] font-bold",
            c.correct ? "bg-exec-soft text-exec" : "bg-active-soft text-active",
          )}
          aria-label={c.correct ? "correct" : "wrong"}
        >
          {c.correct ? "✓" : "✗"}
        </span>
        <span className="font-mono text-[13px] tabular text-muted">Case {pad2(c.number)}</span>
        <span className="font-mono text-[14px] text-ink-2">{problem?.problem_id}</span>
        <span className="truncate text-[15px] text-muted">{outcome}</span>
        <ChevronDown
          strokeWidth={1.5}
          className={cn("ml-auto size-5 shrink-0 text-muted transition-transform", open && "rotate-180")}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease }}
            className="overflow-hidden"
          >
            <div className="border-t border-rule p-3">
              <CaseView c={c} live={false} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
