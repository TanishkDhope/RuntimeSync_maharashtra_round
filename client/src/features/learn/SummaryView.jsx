import { ArrowRight, RotateCcw } from "lucide-react"
import { motion } from "motion/react"
import { useNavigate } from "react-router"

import { Button } from "@/components/Button"
import { DiagnoserTag } from "@/components/ProvenanceTag"
import { cn } from "@/lib/cn"
import { pad2, topicLabel } from "@/lib/format"
import { rise, stagger } from "@/lib/motion"

import { Belief } from "./parts"

/** End of the session: the score, every case, and the beliefs that came up. */
export function SummaryView({ summary, cases, learner }) {
  const navigate = useNavigate()
  const diagnosis = cases.find((c) => c.diagnosis)?.diagnosis

  return (
    <motion.div variants={stagger(0.08)} initial="hidden" animate="shown" className="space-y-6">
      <motion.div variants={rise} className="space-y-3 rounded-panel border border-rule bg-surface px-7 py-7">
        <span className="eyebrow">Session complete · {topicLabel(summary.topic === "mixed" ? null : summary.topic)}</span>
        <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
          <p className="font-serif text-display font-semibold tabular text-ink">
            {summary.correct_count}
            <span className="text-muted">/{summary.total}</span>
          </p>
          <p className="pb-2 text-body text-ink-2">answered correctly{learner ? `, ${learner.name}` : ""}.</p>
        </div>
      </motion.div>

      <motion.div variants={rise} className="overflow-hidden rounded-panel border border-rule bg-surface">
        <div className="border-b border-rule px-6 py-3">
          <span className="eyebrow">Every question</span>
        </div>
        <ol>
          {summary.attempts.map((attempt, i) => (
            <li key={`${attempt.problem_id}-${i}`} className="flex items-center gap-4 border-b border-rule px-6 py-3 last:border-0">
              <span
                className={cn(
                  "grid size-6 shrink-0 place-items-center rounded-full text-[12px] font-bold",
                  attempt.is_correct ? "bg-exec-soft text-exec" : "bg-active-soft text-active",
                )}
              >
                {attempt.is_correct ? "✓" : "✗"}
              </span>
              <span className="font-mono text-[13px] tabular text-muted">{pad2(i + 1)}</span>
              <span className="font-mono text-[14px] text-ink-2">{attempt.problem_id}</span>
              <span className="hidden text-small text-muted sm:inline">
                {attempt.item_type === "write_code" ? "code task" : "predict output"}
              </span>
              <span className="ml-auto truncate text-right font-mono text-[13.5px]">
                {attempt.top_misconception ? (
                  <span className="text-ink-2">{attempt.top_misconception}</span>
                ) : attempt.is_correct ? null : (
                  <span className="font-sans italic text-muted">not narrowed down</span>
                )}
              </span>
            </li>
          ))}
        </ol>
      </motion.div>

      {(summary.misconception_counts.length > 0 || summary.undiagnosed_count > 0) && (
        <motion.div variants={rise} className="space-y-4 rounded-panel border border-rule bg-surface px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="eyebrow">Beliefs that came up</span>
            {diagnosis && <DiagnoserTag diagnosis={diagnosis} />}
          </div>
          <ul className="space-y-4">
            {summary.misconception_counts.map((item) => (
              <li key={item.misconception_id} className="flex items-start gap-4">
                <span className="mt-1 grid h-7 min-w-7 place-items-center rounded-full bg-active-soft px-2 font-mono text-[13px] font-semibold text-active">
                  {item.times}×
                </span>
                <div className="min-w-0">
                  <Belief>{item.description}</Belief>
                  <code className="font-mono text-[13px] text-muted">{item.misconception_id}</code>
                </div>
              </li>
            ))}
          </ul>
          {summary.undiagnosed_count > 0 && (
            <p className="text-small text-muted">
              Counted only where the diagnoser put one belief ahead of the rest. {summary.undiagnosed_count} wrong{" "}
              {summary.undiagnosed_count === 1 ? "answer was" : "answers were"} not narrowed to a single belief.
            </p>
          )}
        </motion.div>
      )}

      <motion.div variants={rise} className="flex flex-wrap gap-3">
        <Button size="lg" onClick={() => navigate("/")} icon={<RotateCcw className="size-[18px]" strokeWidth={1.75} />}>
          Start another session
        </Button>
        {learner && (
          <Button
            size="lg"
            variant="secondary"
            onClick={() => navigate(`/learners/${learner.id}`)}
            icon={<ArrowRight className="size-[18px]" strokeWidth={1.75} />}
          >
            Learner history
          </Button>
        )}
      </motion.div>
    </motion.div>
  )
}
