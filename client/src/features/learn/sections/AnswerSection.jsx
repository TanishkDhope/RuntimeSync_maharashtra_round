import { motion } from "motion/react"

import { CodeBlock } from "@/components/CodeBlock"
import { ProvenanceTag } from "@/components/ProvenanceTag"
import { Section } from "@/components/Section"
import { Tag } from "@/components/Tag"
import { TestResults } from "@/components/TestResults"
import { oneLine, topicLabel } from "@/lib/format"
import { ease } from "@/lib/motion"

import { AnswerForm } from "../AnswerForm"
import { caseProblem } from "../caseModel"
import { PhaseMark, ReasonQuote } from "../parts"

/** 01 · Answer: the question, then (once graded) what the learner said. */
export function AnswerSection({ c, folded, interactive, form }) {
  const problem = caseProblem(c)
  const graded = c.graded
  const writeCode = problem?.item_type === "write_code"

  const summary = !graded
    ? `${problem?.problem_id} · waiting for an answer`
    : graded.is_correct
      ? `Correct · ${writeCode ? "all tests passed" : `“${oneLine(graded.student_response)}”`}`
      : `You wrote “${oneLine(graded.student_response)}” · ${writeCode ? "some tests failed" : "not what it prints"}`

  return (
    <Section
      index={1}
      phase="Answer"
      status={<PhaseMark state={graded ? "done" : "current"} />}
      title={writeCode ? "Write the function" : "What does this program print?"}
      summary={summary}
      folded={folded}
      provenance={
        <>
          <Tag>{topicLabel(problem?.topic)}</Tag>
          <Tag tone="outline" mono>
            {problem?.problem_id}
          </Tag>
        </>
      }
    >
      {!graded && interactive && (
        <AnswerForm
          problem={problem}
          onSubmit={form.onSubmit}
          busy={form.busy}
          busyLabel={form.busyLabel}
          error={form.error}
          autoFocus
        />
      )}

      {!graded && !interactive && problem && (
        writeCode ? <p className="text-body">{problem.problem_text}</p> : <CodeBlock code={problem.problem_text} />
      )}

      {graded && (
        <div className="space-y-5">
          {graded.is_correct && <CorrectBanner writeCode={writeCode} />}
          {writeCode ? (
            <>
              <p className="max-w-[68ch] text-body text-ink">{graded.problem.problem_text}</p>
              <CodeBlock code={graded.student_response} label="your_solution.py" />
              {graded.test_results?.length > 0 && <TestResults results={graded.test_results} />}
            </>
          ) : (
            <>
              <CodeBlock code={graded.problem.problem_text} />
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <span className="text-small font-medium text-muted">You wrote</span>
                  <pre className="rounded-panel border border-rule-strong bg-surface px-4 py-3 font-mono text-code">
                    {graded.student_response || " "}
                  </pre>
                </div>
                {graded.is_correct && (
                  <div className="space-y-1.5">
                    <div className="flex h-5 items-center justify-between">
                      <span className="text-small font-medium text-muted">The program printed</span>
                    </div>
                    <pre className="rounded-panel border border-exec/25 bg-exec-soft/40 px-4 py-3 font-mono text-code">
                      {graded.correct_output}
                    </pre>
                  </div>
                )}
              </div>
            </>
          )}
          <ReasonQuote>{graded.student_explanation}</ReasonQuote>
          {!graded.is_correct && (
            <p className="text-[15px] text-muted">The comparison and the diagnosis are in the next section.</p>
          )}
        </div>
      )}
    </Section>
  )
}

/** A check that draws itself. Kept short: a correct answer should move fast. */
function CorrectBanner({ writeCode }) {
  return (
    <div className="flex items-center gap-4 rounded-panel border border-exec/30 bg-exec-soft px-5 py-4">
      <svg viewBox="0 0 32 32" className="size-9 shrink-0" aria-hidden="true">
        <motion.circle
          cx="16"
          cy="16"
          r="14"
          fill="none"
          stroke="var(--exec)"
          strokeWidth="2"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.45, ease }}
        />
        <motion.path
          d="M10 16.5l4 4 8-9"
          fill="none"
          stroke="var(--exec)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.35, delay: 0.35, ease }}
        />
      </svg>
      <div className="flex-1">
        <p className="font-serif text-h3 font-semibold text-exec">Correct</p>
        <p className="text-[15px] text-ink-2">
          {writeCode ? "Your function passes every test." : "That is exactly what the program prints."}
        </p>
      </div>
      <ProvenanceTag kind="exec" />
    </div>
  )
}
