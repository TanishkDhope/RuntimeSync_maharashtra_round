import { motion } from "motion/react"

import { EmptyState } from "@/components/EmptyState"
import { NumberTicker } from "@/components/NumberTicker"
import { ProvenanceTag } from "@/components/ProvenanceTag"
import { cn } from "@/lib/cn"
import { percent, signedPoints } from "@/lib/format"
import { rise, stagger } from "@/lib/motion"
import { isNotServed, useEvaluation } from "@/lib/queries"

import { BarChart, Heatmap } from "./charts"

const asPercent = (v) => `${(v * 100).toFixed(1)}%`

/**
 * Renders whatever ml/evaluate.py wrote (results/<tag>.json, served by
 * GET /evaluation). Every key is optional; missing ones are skipped. Nothing
 * here is ever a placeholder: no file, no numbers.
 */
export function EvaluationPage() {
  const evaluation = useEvaluation()

  if (evaluation.isPending) {
    return (
      <Frame>
        <div className="h-72 animate-pulse rounded-panel bg-surface-2/70" />
      </Frame>
    )
  }

  const runs = evaluation.data?.runs ?? {}
  if (evaluation.isError || Object.keys(runs).length === 0) {
    return (
      <Frame>
        <EmptyState eyebrow="Model evaluation" title="No evaluation results yet">
          {evaluation.isError && !isNotServed(evaluation.error) ? (
            <p>{evaluation.error.message}</p>
          ) : (
            <>
              <p>
                Results appear here once the model has been evaluated with{" "}
                <code className="font-mono text-[15px]">ml/evaluate.py</code> and the backend serves them at{" "}
                <code className="font-mono text-[15px]">GET /evaluation</code>.
              </p>
              <p className="text-muted">No numbers are shown until then, not even placeholders.</p>
            </>
          )}
        </EmptyState>
      </Frame>
    )
  }

  const tuned = runs.finetuned ?? runs.fine_tuned ?? Object.values(runs).at(-1)
  const base = runs.untuned ?? null
  const runList = [
    base && { key: "untuned", label: "Untuned", tone: "muted", run: base },
    { key: "finetuned", label: "Fine-tuned", tone: "accent", run: tuned },
  ].filter(Boolean)

  return (
    <Frame>
      <motion.header variants={stagger(0.06)} initial="hidden" animate="shown" className="space-y-3">
        <motion.span variants={rise} className="eyebrow block">
          Model evaluation
        </motion.span>
        <motion.h1 variants={rise} className="font-serif text-h1 font-semibold text-ink">
          How well the diagnosis works
        </motion.h1>
        <motion.div variants={rise} className="flex flex-wrap items-center gap-3 text-[15px] text-muted">
          <ProvenanceTag kind="model" />
          {tuned.model && <code className="font-mono text-[14px]">{tuned.model}</code>}
          <span>
            from <code className="font-mono text-[14px]">{evaluation.data.source ?? "results/"}</code>
            {evaluation.data.generated_at && `, ${new Date(evaluation.data.generated_at).toLocaleString()}`}
          </span>
        </motion.div>
      </motion.header>

      <Headlines tuned={tuned} base={base} />

      <AccuracySection runList={runList} tuned={tuned} />
      <ConfusableSection tuned={tuned} />
      <UnknownSection tuned={tuned} />
      <ThresholdSection tuned={tuned} />
      {tuned.confusion?.labels?.length > 0 && (
        <Panel title="Confusion between beliefs" note="Rows: true belief. Columns: the model's first choice.">
          <Heatmap labels={tuned.confusion.labels} matrix={tuned.confusion.matrix} />
        </Panel>
      )}
    </Frame>
  )
}

function Frame({ children }) {
  return <div className="mx-auto max-w-[1100px] space-y-10 px-6 py-10 lg:px-10 lg:py-14">{children}</div>
}

function Headlines({ tuned, base }) {
  const items = [
    {
      label: "Top-1 on new problems",
      sub: "misconceptions seen in training",
      value: tuned.seen_misconceptions_new_problems?.top1,
      before: base?.seen_misconceptions_new_problems?.top1,
      n: tuned.seen_misconceptions_new_problems?.n,
    },
    {
      label: "Top-3 on new problems",
      sub: "right belief in the top three",
      value: tuned.seen_misconceptions_new_problems?.top3,
      before: base?.seen_misconceptions_new_problems?.top3,
      n: tuned.seen_misconceptions_new_problems?.n,
    },
    {
      label: "Top-1 on unseen misconceptions",
      sub: "held out of training entirely",
      value: tuned.held_out_misconceptions_descriptions_added?.top1,
      before: base?.held_out_misconceptions_descriptions_added?.top1,
      n: tuned.held_out_misconceptions_descriptions_added?.n,
    },
  ].filter((item) => item.value != null)

  if (!items.length) return null
  return (
    <motion.div
      variants={stagger(0.08, 0.1)}
      initial="hidden"
      animate="shown"
      className="grid overflow-hidden rounded-panel border border-rule bg-surface sm:grid-cols-3"
    >
      {items.map((item) => (
        <motion.div key={item.label} variants={rise} className="space-y-1 border-b border-rule px-6 py-6 last:border-0 sm:border-b-0 sm:border-r">
          <p className="text-[15px] font-medium text-ink">{item.label}</p>
          <p className="text-small text-muted">{item.sub}</p>
          <NumberTicker
            value={item.value}
            format={asPercent}
            className="block pt-2 font-serif text-[52px] font-semibold leading-none tabular text-ink"
          />
          <p className="flex flex-wrap gap-x-3 pt-1 text-small">
            {item.before != null && (
              <span className={cn("font-medium", item.value - item.before >= 0 ? "text-exec" : "text-active")}>
                {signedPoints(item.value - item.before)} vs untuned
              </span>
            )}
            {item.n != null && <span className="text-muted">n = {item.n}</span>}
          </p>
        </motion.div>
      ))}
    </motion.div>
  )
}

function Panel({ title, note, children }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.42 }}
      className="space-y-5 rounded-panel border border-rule bg-surface px-6 py-6 sm:px-7"
    >
      <div className="space-y-1">
        <h2 className="font-serif text-h3 font-semibold text-ink">{title}</h2>
        {note && <p className="max-w-[72ch] text-[15px] text-muted">{note}</p>}
      </div>
      {children}
    </motion.section>
  )
}

function AccuracySection({ runList, tuned }) {
  const rows = []
  const accuracyRow = (label, sub, pick, field) => {
    const bars = runList
      .map(({ key, label: runLabel, tone, run }) => ({ key, label: runLabel, tone, value: pick(run)?.[field] }))
      .filter((bar) => bar.value != null)
    if (bars.length) rows.push({ label, sub, bars })
  }
  accuracyRow("Seen misconceptions · top-1", "new problems", (r) => r.seen_misconceptions_new_problems, "top1")
  accuracyRow("Seen misconceptions · top-3", "new problems", (r) => r.seen_misconceptions_new_problems, "top3")
  accuracyRow("Unseen misconceptions · top-1", "descriptions added", (r) => r.held_out_misconceptions_descriptions_added, "top1")
  accuracyRow("Unseen misconceptions · top-3", "descriptions added", (r) => r.held_out_misconceptions_descriptions_added, "top3")
  if (tuned.real_responses?.top1 != null) {
    rows.push({
      label: "Real student responses · top-1",
      sub: `n = ${tuned.real_responses.n}`,
      bars: [{ key: "real", label: "Fine-tuned", tone: "accent", value: tuned.real_responses.top1 }],
    })
  }

  const baselines = []
  if (tuned.baseline_lookup_table?.top1 != null) {
    baselines.push({
      label: "Lookup table",
      sub: `(problem, wrong answer) seen in training · covers ${tuned.baseline_lookup_table.covered} of ${tuned.baseline_lookup_table.n}`,
      bars: [{ key: "lookup", label: "Lookup", tone: "muted", value: tuned.baseline_lookup_table.top1 }],
    })
  }
  if (tuned.baseline_llm_zero_shot?.top1 != null) {
    baselines.push({
      label: "LLM zero-shot",
      sub: tuned.baseline_llm_zero_shot.model ?? "picks from the list",
      bars: [{ key: "llm", label: "LLM", tone: "muted", value: tuned.baseline_llm_zero_shot.top1 }],
    })
  }
  if (tuned.ablation_no_reason?.seen?.top1 != null) {
    baselines.push({
      label: "Fine-tuned without the reason",
      sub: "same model, student's explanation removed",
      bars: [{ key: "ablation", label: "No reason", tone: "muted", value: tuned.ablation_no_reason.seen.top1 }],
    })
  }
  const ftTop1 = tuned.seen_misconceptions_new_problems?.top1
  if (baselines.length && ftTop1 != null) {
    baselines.unshift({
      label: "Fine-tuned model",
      sub: "seen misconceptions, new problems",
      bars: [{ key: "ft", label: "Fine-tuned", tone: "accent", value: ftTop1 }],
    })
  }

  if (!rows.length && !baselines.length) return null
  return (
    <>
      {rows.length > 0 && (
        <Panel
          title="Accuracy on problems it never saw"
          note="Every test problem is new to the model. Unseen misconceptions were held out of training entirely; their one-line descriptions are added to the library only at test time."
        >
          <BarChart rows={rows} legend={runList.map(({ key, label, tone }) => ({ key, label, tone }))} />
        </Panel>
      )}
      {baselines.length > 1 && (
        <Panel title="Against the baselines" note="Top-1 accuracy. The lookup table only knows answers it saw in training, which is why a model is needed for new problems.">
          <BarChart rows={baselines} />
        </Panel>
      )}
    </>
  )
}

function ConfusableSection({ tuned }) {
  const group = tuned.within_confusable_groups
  if (!group || group.without_probe == null) return null
  return (
    <Panel
      title="Telling look-alike misconceptions apart"
      note={`Ranking only within each confusable group (n = ${group.n}). With a probe: one follow-up question whose answer differs between the top two.`}
    >
      <BarChart
        rows={[
          { label: "Without a probe", bars: [{ key: "without", label: "Without", tone: "muted", value: group.without_probe }] },
          ...(group.with_simulated_probe != null
            ? [{ label: "With a probe", sub: "simulated", bars: [{ key: "with", label: "With", tone: "accent", value: group.with_simulated_probe }] }]
            : []),
        ]}
      />
      {group.note && <p className="text-small text-muted">{group.note}</p>}
    </Panel>
  )
}

function UnknownSection({ tuned }) {
  const u = tuned.unknown_detection
  if (!u || (u.held_out_flagged_unknown == null && u.seen_wrongly_flagged_unknown == null)) return null
  return (
    <Panel
      title="Saying “I don't know”"
      note="With the unseen misconceptions removed from the library, how often the model correctly answers “unknown”, and how often it raises a false alarm on misconceptions it does know."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {u.held_out_flagged_unknown != null && (
          <Stat label="Unseen, correctly flagged unknown" hint="higher is better" value={u.held_out_flagged_unknown} tone="text-exec" />
        )}
        {u.seen_wrongly_flagged_unknown != null && (
          <Stat label="Known, wrongly flagged unknown" hint="lower is better" value={u.seen_wrongly_flagged_unknown} tone="text-active" />
        )}
      </div>
    </Panel>
  )
}

function Stat({ label, hint, value, tone }) {
  return (
    <div className="rounded-panel border border-rule px-5 py-4">
      <p className="text-[15px] font-medium text-ink">{label}</p>
      <p className="text-small text-muted">{hint}</p>
      <NumberTicker value={value} format={asPercent} className={cn("mt-2 block font-serif text-[40px] font-semibold leading-none tabular", tone)} />
    </div>
  )
}

function ThresholdSection({ tuned }) {
  const t = tuned.thresholds
  if (!t) return null
  const rows = [
    ["Unknown below", t.unknown_below, "top score under this means “unknown”", (v) => v.toFixed(3)],
    ["Balanced accuracy at that cut", t.unknown_val_balanced_acc, "on the validation split", (v) => percent(v)],
    ["Probe gap", t.probe_gap, "top-two gap under this triggers a follow-up question", (v) => v.toFixed(2)],
  ].filter(([, value]) => value != null)
  return (
    <Panel title="Thresholds the app runs on" note="Tuned on the validation split, never on test.">
      <dl className="divide-y divide-rule rounded-panel border border-rule">
        {rows.map(([label, value, hint, fmt]) => (
          <div key={label} className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3">
            <dt>
              <span className="text-[15px] font-medium text-ink">{label}</span>
              <span className="ml-2 text-small text-muted">{hint}</span>
            </dt>
            <dd className="font-mono text-[17px] tabular text-ink">{fmt(value)}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  )
}
