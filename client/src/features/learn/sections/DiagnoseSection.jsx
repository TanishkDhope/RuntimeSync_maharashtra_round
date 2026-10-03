import { HelpCircle, Split } from "lucide-react"
import { motion } from "motion/react"

import { Notice } from "@/components/Notice"
import { NumberTicker } from "@/components/NumberTicker"
import { OutputDiff } from "@/components/OutputDiff"
import { DiagnoserTag, ProvenanceTag } from "@/components/ProvenanceTag"
import { ScoreBar } from "@/components/ScoreBar"
import { Section } from "@/components/Section"
import { Tag } from "@/components/Tag"
import { TestResults } from "@/components/TestResults"
import { cn } from "@/lib/cn"
import { score } from "@/lib/format"
import { ease, rise } from "@/lib/motion"

import { readDiagnosis } from "../caseModel"
import { Belief, PhaseMark, ReasonQuote } from "../parts"

/** 02 · Diagnose: the evidence, then the ranked beliefs, exactly as scored. */
export function DiagnoseSection({ c, folded }) {
  const { graded, diagnosis } = c
  const d = readDiagnosis(diagnosis)
  const unknown = Boolean(c.unknown) || (d.unknown && !d.flat)
  const writeCode = graded.problem.item_type === "write_code"

  const title = unknown
    ? "No belief in the library fits"
    : d.flat
      ? "The beliefs this problem can involve"
      : d.closeCall
        ? "Too close to call"
        : "The belief that best explains this"

  const summary = unknown
    ? "No library match"
    : d.flat
      ? "Not ranked"
      : d.closeCall
        ? `${d.top.misconception_id} vs ${d.second.misconception_id} · too close to call`
        : d.top
          ? `${d.top.misconception_id} · ${score(d.top.score)}`
          : "No candidates"

  return (
    <Section
      index={2}
      phase="Diagnose"
      status={<PhaseMark state="done" />}
      title={title}
      summary={summary}
      folded={folded}
      provenance={<DiagnoserTag diagnosis={diagnosis} />}
    >
      <div className="space-y-5">
        {writeCode ? (
          graded.test_results?.length > 0 && <TestResults results={graded.test_results} />
        ) : (
          <OutputDiff student={graded.student_response} real={graded.correct_output} />
        )}
        <ReasonQuote>{graded.student_explanation}</ReasonQuote>
      </div>

      <div className="h-px bg-rule" />

      {unknown ? (
        <UnknownMatch c={c} d={d} />
      ) : d.flat ? (
        <>
          <Notice icon={<HelpCircle className="size-[18px]" strokeWidth={1.5} />} title="Not a ranking">
            {diagnosis.diagnoser_is_real_model
              ? "The model scored every candidate the same, so this answer doesn't point at one belief more than another."
              : "The stub diagnoser can only match predicted outputs, so it can't rank a code answer. These are the beliefs this problem can involve, not a diagnosis."}
          </Notice>
          <CandidateList candidates={d.candidates} topScore={d.top.score} dimAll />
        </>
      ) : (
        <Hypotheses d={d} diagnosis={diagnosis} />
      )}
    </Section>
  )
}

function Hypotheses({ d, diagnosis }) {
  const { candidates, closeCall, gap } = d
  const topScore = Math.max(1, candidates[0]?.score ?? 1)

  if (!closeCall) return <CandidateList candidates={candidates} topScore={topScore} />

  const threshold = diagnosis.probe_gap
  return (
    <div className="space-y-4">
      <Notice tone="warn" icon={<Split className="size-[18px] text-improving" strokeWidth={1.5} />} title="Too close to call">
        The top two beliefs score within{" "}
        <span className="font-mono tabular">
          Δ {gap.toFixed(2)}
          {threshold != null && ` < ${threshold.toFixed(2)}`}
        </span>{" "}
        of each other, so this answer alone can't separate them. One follow-up question that they answer
        differently will.
      </Notice>
      <div className="relative pl-7">
        <Bracket />
        <CandidateList candidates={candidates.slice(0, 2)} topScore={topScore} tighten />
      </div>
      {candidates.length > 2 && (
        <CandidateList candidates={candidates.slice(2)} topScore={topScore} startIndex={2} />
      )}
    </div>
  )
}

/** The bracket that groups the two candidates a probe will separate. */
function Bracket() {
  return (
    <motion.span
      aria-hidden="true"
      className="absolute bottom-3 left-0 top-3 w-3.5 origin-center rounded-l-[6px] border-y-2 border-l-2 border-improving"
      initial={{ scaleY: 0, opacity: 0 }}
      animate={{ scaleY: 1, opacity: 1 }}
      transition={{ duration: 0.5, delay: 0.5, ease }}
    />
  )
}

/** `tighten` pulls the rows together after they arrive (the close-call pair). */
function listVariants(tighten) {
  return {
    hidden: { rowGap: tighten ? 28 : 16 },
    shown: {
      rowGap: tighten ? 10 : 16,
      transition: {
        staggerChildren: 0.08,
        delayChildren: 0.15,
        rowGap: { duration: 0.5, delay: 0.75, ease },
      },
    },
  }
}

function CandidateList({ candidates, topScore, startIndex = 0, dimAll = false, tighten = false }) {
  return (
    <motion.ol variants={listVariants(tighten)} initial="hidden" animate="shown" className="flex flex-col">
      {candidates.map((candidate, i) => {
        const rank = startIndex + i
        const lead = rank === 0 && !dimAll
        return (
          <motion.li key={candidate.misconception_id} variants={rise} className="space-y-2">
            <div className="flex items-start gap-4">
              <span
                className={cn(
                  "mt-1 grid size-7 shrink-0 place-items-center rounded-full font-mono text-[13px] font-semibold",
                  lead ? "bg-accent text-on-accent" : "bg-surface-2 text-muted",
                )}
              >
                {rank + 1}
              </span>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex items-start justify-between gap-4">
                  <Belief className={cn(!lead && "text-ink-2")}>{candidate.description}</Belief>
                  <NumberTicker
                    value={candidate.score}
                    delay={0.15 + i * 0.08}
                    className={cn("mt-1 shrink-0 font-mono text-[17px] tabular", lead ? "text-ink" : "text-muted")}
                  />
                </div>
                <ScoreBar value={candidate.score} max={topScore} delay={0.15 + i * 0.08} tone={lead ? "accent" : "muted"} />
                <div className="flex flex-wrap items-center gap-2">
                  <code className="font-mono text-[13.5px] text-muted">{candidate.misconception_id}</code>
                  {candidate.confusable_group && (
                    <Tag tone="outline" className="h-6 text-[13px]">
                      confusable · {candidate.confusable_group.toLowerCase().replaceAll("_", " ")}
                    </Tag>
                  )}
                </div>
              </div>
            </div>
          </motion.li>
        )
      })}
    </motion.ol>
  )
}

function UnknownMatch({ c, d }) {
  const threshold = c.diagnosis.unknown_threshold
  const draft = c.unknown?.draft
  return (
    <div className="space-y-5">
      <motion.div
        variants={rise}
        initial="hidden"
        animate="shown"
        className="rounded-panel border-2 border-dashed border-rule-strong px-5 py-5"
      >
        <p className="font-serif text-h3 text-ink">Nothing in the library explains this answer well.</p>
        {d.top && (
          <p className="mt-1 text-[15px] text-ink-2">
            The closest belief, <code className="font-mono text-[14px]">{d.top.misconception_id}</code>, scored{" "}
            <span className="font-mono tabular">{score(d.top.score)}</span>
            {threshold != null ? (
              <>
                , below the <span className="font-mono tabular">{score(threshold)}</span> needed to name it.
              </>
            ) : (
              ", below the threshold needed to name it."
            )}{" "}
            It could be a careless slip, or a misconception the library doesn't cover yet.
          </p>
        )}
      </motion.div>

      {draft && (
        <motion.div
          variants={rise}
          initial="hidden"
          animate="shown"
          className="space-y-3 rounded-panel border border-dashed border-muted/60 px-5 py-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="eyebrow">Draft belief for review</span>
            <ProvenanceTag kind="llm" label="Generated · draft" />
          </div>
          <Belief size="lg">{draft.description}</Belief>
          <p className="text-small text-muted">
            Saved for a teacher to review. It is not added to the library, and the model is not retrained on it.
          </p>
        </motion.div>
      )}

      {d.candidates.length > 0 && (
        <div className="space-y-3 opacity-80">
          <span className="text-small font-medium text-muted">Closest matches, none close enough</span>
          <CandidateList candidates={d.candidates} topScore={Math.max(1, d.top.score)} dimAll />
        </div>
      )}
    </div>
  )
}
