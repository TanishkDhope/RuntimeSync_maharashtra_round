import { motion } from "motion/react"
import { Link } from "react-router"

import { Tag } from "@/components/Tag"
import { cn } from "@/lib/cn"
import { pad2, topicLabel } from "@/lib/format"
import { spring } from "@/lib/motion"

import { caseProblem, PHASE_LABEL, PHASES, phaseStates } from "./caseModel"

/**
 * The case at a glance: six phases, which are done, which is on screen, and
 * which were skipped and why. Skipped phases stay visible on purpose: they
 * show the flow adapting to the answer.
 */
export function CaseRail({ c, progress, learner, summary }) {
  const states = c ? phaseStates(c) : null
  const problem = c ? caseProblem(c) : null

  return (
    <aside className="lg:sticky lg:top-[88px] lg:self-start">
      <div className="space-y-6 lg:space-y-7">
        <div className="space-y-2">
          <span className="eyebrow">
            {summary ? "Session complete" : progress ? `Session · question ${progress.index} of ${progress.total}` : "Session"}
          </span>
          {c && !summary && (
            <>
              <p className="font-serif text-h2 font-semibold text-ink">Case {pad2(c.number)}</p>
              <div className="flex flex-wrap gap-1.5">
                {problem && <Tag>{topicLabel(problem.topic)}</Tag>}
                {problem && (
                  <Tag tone="outline" mono>
                    {problem.problem_id}
                  </Tag>
                )}
              </div>
            </>
          )}
        </div>

        {states && !summary && (
          <ol className="relative hidden space-y-1 lg:block" aria-label="Phases of this case">
            <span aria-hidden="true" className="absolute bottom-4 left-[13px] top-4 w-px bg-rule" />
            {PHASES.map((phase, i) => (
              <PhaseRow key={phase} index={i + 1} label={PHASE_LABEL[phase]} {...states[phase]} />
            ))}
          </ol>
        )}

        {states && !summary && <CompactPhases states={states} />}

        {learner && (
          <div className="hidden border-t border-rule pt-5 lg:block">
            <span className="text-small text-muted">Learning as</span>
            <p className="text-[16px] font-medium text-ink">{learner.name}</p>
            <Link
              to={`/learners/${learner.id}`}
              className="mt-1 inline-block text-small font-medium text-accent underline-offset-4 hover:underline"
            >
              Learner history →
            </Link>
          </div>
        )}
      </div>
    </aside>
  )
}

function PhaseRow({ index, label, state, note, focus }) {
  const skipped = state === "skipped" || state === "unavailable"
  return (
    <li className="relative flex gap-3.5 py-1.5" aria-current={focus ? "step" : undefined}>
      <span className="relative z-10 grid size-[27px] shrink-0 place-items-center">
        <Marker state={state} />
        {focus && (
          <motion.span
            layoutId="rail-focus"
            transition={spring}
            className="absolute -inset-[5px] rounded-full border-2 border-accent"
          />
        )}
      </span>
      <span className="min-w-0 pt-[3px]">
        <span
          className={cn(
            "block text-[15px] leading-tight",
            focus ? "font-semibold text-ink" : state === "done" ? "text-ink-2" : "text-muted",
            skipped && "line-through decoration-muted/60",
          )}
        >
          <span className="mr-1.5 font-mono text-[12px] tabular text-muted no-underline">{pad2(index)}</span>
          {label}
        </span>
        {note && <span className="mt-0.5 block text-[13px] leading-snug text-muted">{note}</span>}
      </span>
    </li>
  )
}

function Marker({ state }) {
  if (state === "done") {
    return (
      <span className="grid size-[19px] place-items-center rounded-full bg-exec text-[11px] font-bold text-white dark:text-paper">
        ✓
      </span>
    )
  }
  if (state === "current") return <span className="size-[11px] rounded-full bg-accent" />
  if (state === "skipped" || state === "unavailable") {
    return <span className="h-[2px] w-[11px] rounded-full bg-muted/60" />
  }
  return <span className="size-[11px] rounded-full border-2 border-rule-strong bg-paper" />
}

/** Below lg the rail becomes a horizontal stepper. */
function CompactPhases({ states }) {
  return (
    <ol className="flex flex-wrap gap-x-4 gap-y-2 lg:hidden" aria-label="Phases of this case">
      {PHASES.map((phase) => {
        const { state, note, focus } = states[phase]
        return (
          <li
            key={phase}
            title={note}
            className={cn(
              "flex items-center gap-1.5 text-small",
              focus ? "font-semibold text-ink" : state === "done" ? "text-ink-2" : "text-muted",
              (state === "skipped" || state === "unavailable") && "line-through",
            )}
          >
            <Marker state={state} />
            {PHASE_LABEL[phase]}
          </li>
        )
      })}
    </ol>
  )
}
