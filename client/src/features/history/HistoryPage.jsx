import { motion } from "motion/react"
import { Fragment, useMemo, useState } from "react"
import { Link, useParams } from "react-router"

import { ChevronRight } from "lucide-react"

import { EmptyState } from "@/components/EmptyState"
import { BeliefGraph } from "./BeliefGraph"
import { TopicMastery } from "./TopicMastery"
import { StatusChip } from "@/components/StatusChip"
import { Tag } from "@/components/Tag"
import { cn } from "@/lib/cn"
import { timeAgo, topicLabel } from "@/lib/format"
import { rise, stagger } from "@/lib/motion"
import { isNotServed, useBeliefEvidence, useHistory } from "@/lib/queries"

const ORDER = { active: 0, improving: 1, resolved: 2 }

/** The learner model: every belief seen, its status, and the attempt timeline. */
export function HistoryPage() {
  const learnerId = Number(useParams().learnerId)
  const history = useHistory(learnerId)

  if (history.isPending) return <PageFrame><div className="h-80 animate-pulse rounded-panel bg-surface-2/70" /></PageFrame>

  if (history.isError) {
    return (
      <PageFrame>
        <EmptyState
          eyebrow="Learner history"
          title={isNotServed(history.error) ? "History isn't served by the backend yet" : "History couldn't be loaded"}
        >
          {isNotServed(history.error) ? (
            <p>
              This page reads <code className="font-mono text-[15px]">GET /learners/{learnerId}/history</code>, which the
              backend doesn't have yet. The shape it expects is in <code className="font-mono text-[15px]">client/API_CONTRACT.md</code>.
            </p>
          ) : (
            <p>{history.error.message}</p>
          )}
        </EmptyState>
      </PageFrame>
    )
  }

  const { learner, beliefs, attempts, topic_mastery: topicMastery } = history.data
  return (
    <PageFrame>
      <Overview learner={learner} beliefs={beliefs} attempts={attempts} />
      <TopicMastery topics={topicMastery} />
      <BeliefGraph learnerId={learnerId} />
      <BeliefLedger beliefs={beliefs} learnerId={learnerId} />
      <AttemptTimeline attempts={attempts} />
    </PageFrame>
  )
}

function PageFrame({ children }) {
  return <div className="mx-auto max-w-[1100px] space-y-8 px-6 py-10 lg:px-10 lg:py-14">{children}</div>
}

function Overview({ learner, beliefs, attempts }) {
  const counts = { active: 0, improving: 0, resolved: 0 }
  beliefs.forEach((belief) => (counts[belief.status] += 1))
  const correct = attempts.filter((a) => a.is_correct).length

  return (
    <motion.header variants={stagger(0.06)} initial="hidden" animate="shown" className="space-y-6">
      <motion.div variants={rise} className="space-y-2">
        <span className="eyebrow">Learner model</span>
        <h1 className="font-serif text-h1 font-semibold text-ink">{learner.name}</h1>
        <p className="text-body text-muted">
          {attempts.length} attempts, {correct} correct · joined {timeAgo(learner.created_at)}
        </p>
      </motion.div>
      <motion.dl variants={rise} className="grid grid-cols-3 overflow-hidden rounded-panel border border-rule bg-surface">
        {[
          ["active", "Still active", "text-active"],
          ["improving", "Improving", "text-improving"],
          ["resolved", "Resolved", "text-exec"],
        ].map(([key, label, tone]) => (
          <div key={key} className="border-r border-rule px-6 py-5 last:border-0">
            <dt className="text-small font-medium text-muted">{label}</dt>
            <dd className={cn("font-serif text-[40px] font-semibold leading-tight tabular", tone)}>{counts[key]}</dd>
          </div>
        ))}
      </motion.dl>
    </motion.header>
  )
}

function BeliefLedger({ beliefs, learnerId }) {
  const sorted = useMemo(
    () => [...beliefs].sort((a, b) => ORDER[a.status] - ORDER[b.status] || b.times_seen - a.times_seen),
    [beliefs],
  )
  // Which belief is showing its working. One at a time: the point is to read
  // the trail, not to compare six of them.
  const [opened, setOpened] = useState(null)
  return (
    <motion.section variants={rise} initial="hidden" animate="shown" className="overflow-hidden rounded-panel border border-rule bg-surface">
      <div className="flex items-center justify-between border-b border-rule px-6 py-4">
        <h2 className="font-serif text-h3 font-semibold text-ink">Beliefs</h2>
        <span className="text-small text-muted">recurring misconceptions and demonstrated understanding</span>
      </div>
      {sorted.length === 0 ? (
        <p className="px-6 py-8 text-body text-muted">No misconceptions diagnosed yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <thead>
              <tr className="border-b border-rule text-small text-muted">
                <th className="px-6 py-2.5 font-medium">Belief</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Seen</th>
                <th className="px-4 py-2.5 font-medium">Last seen</th>
                <th className="px-4 py-2.5 font-medium sr-only">Evidence</th>
              </tr>
            </thead>
            <motion.tbody variants={stagger(0.05)} initial="hidden" animate="shown">
              {sorted.map((belief) => (
                <Fragment key={belief.misconception_id}>
                <motion.tr
                  variants={rise}
                  onClick={() => setOpened(opened === belief.misconception_id ? null : belief.misconception_id)}
                  className={cn(
                    "cursor-pointer border-b border-rule align-top transition-colors last:border-0",
                    opened === belief.misconception_id ? "bg-surface-2/60" : "hover:bg-surface-2/40",
                  )}
                >
                  <td className="px-6 py-4">
                    <p className="font-serif text-[18px] leading-snug text-ink">“{belief.description}”</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      <code className="font-mono text-[13px] text-muted">{belief.misconception_id}</code>
                      {belief.topic && <Tag className="h-6 text-[13px]">{topicLabel(belief.topic)}</Tag>}
                      {belief.returned && (
                        <Tag className="h-6 bg-active-soft text-[13px] text-active">came back after resolving</Tag>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <StatusChip status={belief.status} />
                    {belief.resolved_at && belief.status === "resolved" && (
                      <p className="mt-1.5 text-[13px] text-muted">resolved {timeAgo(belief.resolved_at)}</p>
                    )}
                    {belief.status === "improving" && belief.evidence_needed > 0 && (
                      <EvidenceMeter have={belief.evidence_against} need={belief.evidence_needed} />
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <SeenDots count={belief.times_seen} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 text-small text-ink-2">{timeAgo(belief.last_seen)}</td>
                  <td className="px-4 py-4">
                    <ChevronRight
                      aria-hidden="true"
                      className={cn(
                        "size-4 text-muted transition-transform",
                        opened === belief.misconception_id && "rotate-90",
                      )}
                    />
                    <span className="sr-only">
                      {opened === belief.misconception_id ? "Hide" : "Show"} the evidence behind this belief
                    </span>
                  </td>
                </motion.tr>
                {opened === belief.misconception_id && (
                  <tr className="border-b border-rule last:border-0">
                    <td colSpan={5} className="bg-surface-2/40 px-6 py-4">
                      <EvidenceTrail learnerId={learnerId} belief={belief} />
                    </td>
                  </tr>
                )}
                </Fragment>
              ))}
            </motion.tbody>
          </table>
        </div>
      )}
    </motion.section>
  )
}

/** How far along a belief is towards being called resolved. */
function EvidenceMeter({ have, need }) {
  const pct = Math.min(100, Math.round((have / need) * 100))
  return (
    <div className="mt-2 w-28">
      <div className="h-1 overflow-hidden rounded-full bg-rule">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1 text-[13px] text-muted">
        {have.toFixed(1)} of {need.toFixed(1)} evidence
      </p>
    </div>
  )
}

/** Why this belief stands where it does: the answers that moved it, in order. */
function EvidenceTrail({ learnerId, belief }) {
  const trail = useBeliefEvidence(learnerId, belief.misconception_id, true)

  if (trail.isPending) return <p className="text-small text-muted">Reading the evidence…</p>
  if (trail.error) {
    return (
      <p className="text-small text-muted">
        {isNotServed(trail.error)
          ? "This backend doesn't serve the evidence trail yet."
          : "Couldn't load the evidence behind this belief."}
      </p>
    )
  }
  if (!trail.data?.length) {
    return <p className="text-small text-muted">No evidence recorded for this belief yet.</p>
  }

  return (
    <div className="space-y-2">
      <p className="text-small text-muted">
        Every answer that moved this belief. A wrong answer diagnosed here counts against it being gone;
        a correct one on a problem that tests it counts towards.
      </p>
      <ol className="space-y-1.5">
        {trail.data.map((row, index) => (
          <li key={`${row.problem_id}-${index}`} className="flex flex-wrap items-center gap-2 text-small">
            <Tag
              className={cn(
                "h-6 text-[13px]",
                row.direction === "for" ? "bg-active-soft text-active" : "bg-accent-soft text-accent",
              )}
            >
              {row.direction === "for" ? "showed up" : `cleared +${row.weight.toFixed(2)}`}
            </Tag>
            <code className="font-mono text-[13px] text-muted">{row.problem_id}</code>
            {row.phase === "reassess" && <span className="text-[13px] text-muted">retest</span>}
            <span className="ml-auto text-[13px] text-muted">{timeAgo(row.created_at)}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function SeenDots({ count }) {
  const shown = Math.min(count, 8)
  return (
    <span className="flex items-center gap-1.5" aria-label={`seen ${count} times`}>
      <span className="flex gap-[3px]">
        {Array.from({ length: shown }, (_, i) => (
          <span key={i} className="size-2 rounded-full bg-ink-2/70" />
        ))}
      </span>
      <span className="font-mono text-small tabular text-ink-2">{count}</span>
    </span>
  )
}

const PHASE_SHAPE = {
  initial: "rounded-full",
  probe: "rotate-45 rounded-[2px]",
  reassess: "rounded-[2px]",
}

/** One lane per session; shape = phase, colour = right or wrong. */
function AttemptTimeline({ attempts }) {
  const [hover, setHover] = useState(null)
  const sessions = useMemo(() => {
    const bySession = new Map()
    for (const attempt of [...attempts].sort((a, b) => a.created_at.localeCompare(b.created_at))) {
      if (!bySession.has(attempt.session_id)) bySession.set(attempt.session_id, [])
      bySession.get(attempt.session_id).push(attempt)
    }
    return [...bySession.entries()].reverse()
  }, [attempts])

  return (
    <motion.section variants={rise} initial="hidden" animate="shown" className="rounded-panel border border-rule bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-6 py-4">
        <h2 className="font-serif text-h3 font-semibold text-ink">Attempts</h2>
        <Legend />
      </div>
      {sessions.length === 0 ? (
        <p className="px-6 py-8 text-body text-muted">No attempts yet.</p>
      ) : (
        <div className="space-y-1 px-6 py-5">
          {sessions.map(([sessionId, rows]) => (
            <div key={sessionId} className="flex items-center gap-5 py-1.5">
              <Link
                to={`/learn/${sessionId}`}
                title="Open this session's summary"
                className="w-24 shrink-0 font-mono text-[13px] tabular text-muted underline-offset-4 hover:text-ink hover:underline"
              >
                Session {sessionId}
              </Link>
              <div className="relative flex flex-1 flex-wrap items-center gap-2.5">
                <span aria-hidden="true" className="absolute inset-x-0 top-1/2 h-px bg-rule" />
                {rows.map((attempt) => (
                  <button
                    key={attempt.id}
                    type="button"
                    onMouseEnter={() => setHover(attempt)}
                    onMouseLeave={() => setHover(null)}
                    onFocus={() => setHover(attempt)}
                    onBlur={() => setHover(null)}
                    aria-label={`${attempt.problem_id}, ${attempt.phase}, ${attempt.is_correct ? "correct" : "wrong"}`}
                    className="relative grid size-6 place-items-center"
                  >
                    <span
                      className={cn(
                        "size-3.5 transition-transform hover:scale-125",
                        PHASE_SHAPE[attempt.phase],
                        attempt.is_correct ? "bg-exec" : "bg-active",
                      )}
                    />
                  </button>
                ))}
              </div>
            </div>
          ))}
          <div className="min-h-[52px] pt-3 text-small text-ink-2" aria-live="polite">
            {hover ? (
              <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <code className="font-mono text-[14px] text-ink">{hover.problem_id}</code>
                <span>{hover.phase === "initial" ? "first answer" : hover.phase}</span>
                <span className={hover.is_correct ? "text-exec" : "text-active"}>
                  {hover.is_correct ? "correct" : "wrong"}
                </span>
                {hover.top_misconception && <code className="font-mono text-[13.5px] text-muted">{hover.top_misconception}</code>}
                <span className="text-muted">{timeAgo(hover.created_at)}</span>
              </span>
            ) : (
              <span className="text-muted">Point at an attempt for details.</span>
            )}
          </div>
        </div>
      )}
    </motion.section>
  )
}

function Legend() {
  const item = (shape, label) => (
    <span className="flex items-center gap-1.5">
      <span className={cn("size-2.5 bg-ink-2", shape)} />
      {label}
    </span>
  )
  return (
    <div className="flex flex-wrap items-center gap-4 text-small text-muted">
      {item(PHASE_SHAPE.initial, "first answer")}
      {item(PHASE_SHAPE.probe, "probe")}
      {item(PHASE_SHAPE.reassess, "retest")}
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-exec" /> right
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-active" /> wrong
      </span>
    </div>
  )
}
