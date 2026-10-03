import { motion } from "motion/react"

import { ProvenanceTag } from "@/components/ProvenanceTag"
import { Section } from "@/components/Section"
import { cn } from "@/lib/cn"
import { rise } from "@/lib/motion"

import { TraceStepper } from "../TraceStepper"
import { Belief, PhaseMark } from "../parts"

/** 04 · Explain: teaching aimed at the diagnosed belief, plus the real run. */
export function ExplainSection({ c, folded }) {
  const { misconception, explanation, trace } = c.intervention
  const generated = explanation.source === "llm"

  return (
    <Section
      index={4}
      phase="Explain"
      status={<PhaseMark state="done" />}
      title="Where this belief and Python part ways"
      summary={`Explained ${misconception.misconception_id} with a traced run`}
      folded={folded}
    >
      <div className="space-y-1.5">
        <span className="text-small font-medium text-muted">Addressing the belief</span>
        <Belief size="lg">{misconception.description}</Belief>
        <code className="font-mono text-[13.5px] text-muted">{misconception.misconception_id}</code>
      </div>

      <motion.article
        variants={rise}
        initial="hidden"
        animate="shown"
        className={cn(
          "space-y-3 rounded-panel px-6 py-5",
          generated ? "border border-dashed border-muted/60" : "border border-rule bg-surface-2/40",
        )}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="eyebrow">Explanation</span>
          {generated ? <ProvenanceTag kind="llm" label="Generated · Gemini" /> : <ProvenanceTag kind="authored" />}
        </div>
        <div className="max-w-[64ch] space-y-3 font-serif text-[19px] leading-[1.6] text-ink">
          {explanation.text.split(/\n{2,}/).map((paragraph, i) => (
            <p key={i}>{paragraph}</p>
          ))}
        </div>
      </motion.article>

      {trace?.steps?.length > 0 && <TraceStepper trace={trace} />}
    </Section>
  )
}
