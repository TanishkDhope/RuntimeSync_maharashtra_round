import { motion } from "motion/react"

import { CodeBlock } from "@/components/CodeBlock"
import { OutputDiff } from "@/components/OutputDiff"
import { ProvenanceTag } from "@/components/ProvenanceTag"
import { Section } from "@/components/Section"
import { Tag } from "@/components/Tag"
import { TestResults } from "@/components/TestResults"
import { cn } from "@/lib/cn"
import { ordinal, score, topicLabel } from "@/lib/format"
import { rise } from "@/lib/motion"

import { AnswerForm } from "../AnswerForm"
import { PhaseMark, ReasonQuote } from "../parts"

const TRANSFER = {
  different_topic: "Different topic",
  code_task: "Code task",
}

/**
 * 05 · Retest: 2 or 3 unseen problems where the belief would show again.
 * One right answer is not proof, so every item is checked, and the model
 * re-reads the learner's reasons.
 */
export function RetestSection({ c, folded, interactive, form }) {
  const { items } = c.retest
  const total = c.retest.total ?? items.length
  const answered = items.filter((item) => item.result).length
  const right = items.filter((item) => item.result?.graded.is_correct).length

  return (
    <Section
      index={5}
      phase="Retest"
      status={<PhaseMark state={c.verdict ? "done" : "current"} />}
      title="Check it's really gone"
      summary={`${right} of ${answered} correct${answered < total ? ` · ${total - answered} to go` : ""}`}
      folded={folded}
    >
      <Progress total={total} items={items} />

      <div className="space-y-6">
        {items.map((item, i) => {
          const isLast = i === items.length - 1
          const problem = item.ask?.problem ?? item.result?.graded.problem
          return (
            <motion.div key={problem?.problem_id ?? i} variants={rise} initial="hidden" animate="shown" className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-serif text-h3 font-semibold text-ink">Check {i + 1}</span>
                {item.ask?.transfer && <Tag tone="accent">{TRANSFER[item.ask.transfer] ?? item.ask.transfer}</Tag>}
                <Tag>{topicLabel(problem?.topic)}</Tag>
                <Tag tone="outline" mono>
                  {problem?.problem_id}
                </Tag>
              </div>

              {!item.result && isLast && interactive ? (
                <AnswerForm
                  problem={problem}
                  onSubmit={form.onSubmit}
                  busy={form.busy}
                  busyLabel={form.busyLabel}
                  error={form.error}
                  autoFocus
                />
              ) : item.result ? (
                <RetestResult result={item.result} />
              ) : (
                problem && <CodeBlock code={problem.problem_text} />
              )}
              {!isLast && <div className="h-px bg-rule" />}
            </motion.div>
          )
        })}
      </div>
    </Section>
  )
}

function Progress({ total, items }) {
  return (
    <div className="flex items-center gap-2" aria-label={`Retest progress: ${items.length} of ${total}`}>
      {Array.from({ length: total }, (_, i) => {
        const result = items[i]?.result
        return (
          <span
            key={i}
            className={cn(
              "h-2 flex-1 rounded-full transition-colors duration-300",
              !items[i] && "bg-surface-2",
              items[i] && !result && "bg-accent/40",
              result?.graded.is_correct && "bg-exec",
              result && !result.graded.is_correct && "bg-active",
            )}
          />
        )
      })}
    </div>
  )
}

function RetestResult({ result }) {
  const { graded, model_check: check } = result
  const writeCode = graded.problem.item_type === "write_code"
  return (
    <div className="space-y-4">
      {writeCode ? (
        <>
          <CodeBlock code={graded.student_response} label="your_solution.py" />
          {graded.test_results && <TestResults results={graded.test_results} />}
        </>
      ) : (
        <>
          <CodeBlock code={graded.problem.problem_text} />
          <OutputDiff student={graded.student_response} real={graded.correct_output} />
        </>
      )}
      <ReasonQuote>{graded.student_explanation}</ReasonQuote>
      {check && (
        <div className="flex flex-wrap items-center gap-3 rounded-panel border border-rule bg-surface-2/50 px-4 py-3">
          <ProvenanceTag kind="model" />
          <span className="text-[15px] text-ink-2">
            On this reason the model ranks <code className="font-mono text-[14px]">{check.misconception_id}</code>{" "}
            <strong className={cn("font-semibold", check.rank === 1 ? "text-active" : "text-exec")}>
              {ordinal(check.rank)}
            </strong>{" "}
            <span className="font-mono tabular text-muted">({score(check.score)})</span>
          </span>
        </div>
      )}
    </div>
  )
}
