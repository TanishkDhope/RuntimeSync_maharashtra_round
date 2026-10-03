import { Check } from "lucide-react"
import { motion } from "motion/react"

import { CodeBlock } from "@/components/CodeBlock"
import { Notice } from "@/components/Notice"
import { ProvenanceTag } from "@/components/ProvenanceTag"
import { Section } from "@/components/Section"
import { cn } from "@/lib/cn"
import { sameOutput } from "@/lib/diff"
import { ease, rise, stagger } from "@/lib/motion"

import { AnswerForm } from "../AnswerForm"
import { PhaseMark } from "../parts"

/**
 * 03 · Probe: one question whose answer differs under each close candidate.
 * After the answer, a three-way reveal shows which belief it matched.
 */
export function ProbeSection({ c, folded, interactive, form }) {
  const { step, outcome } = c.probe
  const probe = step?.probe
  const describe = (id) =>
    c.diagnosis?.candidates.find((m) => m.misconception_id === id)?.description ?? id
  const ids = probe?.candidates ?? Object.keys(outcome?.predictions ?? {})

  const summary = outcome
    ? outcome.matched
      ? `Your answer matched ${outcome.matched}`
      : "Matched neither belief · diagnosis stays uncertain"
    : "One question to tell them apart"

  return (
    <Section
      index={3}
      phase="Probe"
      status={<PhaseMark state={outcome ? "done" : "current"} />}
      title="One question to tell these apart"
      summary={summary}
      folded={folded}
      tone={probe?.source === "llm" ? "dashed" : undefined}
      provenance={probe && <ProbeSource probe={probe} />}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {ids.slice(0, 2).map((id, i) => (
          <div key={id} className="rounded-panel border border-rule bg-surface-2/50 px-4 py-3">
            <span className="eyebrow">Belief {String.fromCharCode(65 + i)}</span>
            <p className="mt-1 font-serif text-[17px] leading-snug text-ink">“{describe(id)}”</p>
          </div>
        ))}
      </div>

      {!outcome && interactive && probe && (
        <AnswerForm
          problem={probe.problem}
          onSubmit={form.onSubmit}
          busy={form.busy}
          busyLabel={form.busyLabel}
          error={form.error}
          submitLabel="Check this answer"
          autoFocus
        />
      )}

      {!outcome && !interactive && probe && <CodeBlock code={probe.problem.problem_text} />}

      {outcome && <Reveal outcome={outcome} ids={ids} problem={probe?.problem} />}
    </Section>
  )
}

function ProbeSource({ probe }) {
  if (probe.source === "bank") {
    return (
      <>
        <ProvenanceTag kind="bank" />
        {probe.executed && <ProvenanceTag kind="exec" label="Outputs verified" />}
      </>
    )
  }
  return (
    <>
      <ProvenanceTag kind="llm" label="Generated program" />
      <span className="inline-flex h-7 items-center gap-2 text-small text-ink-2">
        <CheckMark ok={probe.executed}>Ran it</CheckMark>
        <CheckMark ok={probe.independent_check}>Independent check</CheckMark>
      </span>
    </>
  )
}

function CheckMark({ ok, children }) {
  return (
    <span className={cn("inline-flex items-center gap-1", ok ? "text-exec" : "text-muted line-through")}>
      {ok && <Check className="size-3.5" strokeWidth={2.25} />}
      {children}
    </span>
  )
}

/** Real output, each belief's prediction, and which one the answer matched. */
function Reveal({ outcome, ids, problem }) {
  const columns = [
    { key: "real", label: "Python prints", text: outcome.real_output, real: true },
    ...ids.map((id, i) => ({
      key: id,
      label: `If belief ${String.fromCharCode(65 + i)}`,
      sub: id,
      text: outcome.predictions[id],
      matched: outcome.matched === id,
    })),
  ]
  const answeredCorrectly = sameOutput(outcome.student_response, outcome.real_output)

  return (
    <div className="space-y-5">
      {problem && <CodeBlock code={problem.problem_text} />}
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="text-small font-medium text-muted">You answered</span>
        <code className="rounded-control bg-surface-2 px-2.5 py-1 font-mono text-[15px] text-ink">
          {outcome.student_response.replace(/\n/g, " ⏎ ")}
        </code>
      </div>
      <motion.div
        variants={stagger(0.12, 0.1)}
        initial="hidden"
        animate="shown"
        className={cn("grid gap-3", columns.length === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2")}
      >
        {columns.map((column) => (
          <motion.div
            key={column.key}
            variants={rise}
            className={cn(
              "relative space-y-2 rounded-panel border px-4 py-3 transition-colors",
              column.real && "border-exec/30 bg-exec-soft/40",
              !column.real && !column.matched && "border-rule bg-surface",
              column.matched && "border-accent bg-accent-soft",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-small font-medium text-ink-2">{column.label}</span>
              {column.real && <ProvenanceTag kind="exec" label="Ran it" className="h-6" />}
            </div>
            {column.sub && <code className="block font-mono text-[12.5px] text-muted">{column.sub}</code>}
            <pre className="font-mono text-code text-ink">{column.text ?? "—"}</pre>
            {column.matched && (
              <motion.span
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6, duration: 0.3, ease }}
                className="inline-flex items-center gap-1.5 text-small font-semibold text-accent"
              >
                <Check className="size-4" strokeWidth={2.25} /> Matches your answer
              </motion.span>
            )}
          </motion.div>
        ))}
      </motion.div>

      {!outcome.matched && (
        <Notice title={answeredCorrectly ? "You got this one right" : "Your answer matched neither belief"}>
          {answeredCorrectly
            ? "Neither candidate belief showed up here, so the diagnosis stays uncertain. The explanation targets the stronger candidate."
            : "The diagnosis stays uncertain. The explanation targets the stronger candidate, and the retest will check it."}
        </Notice>
      )}
    </div>
  )
}
