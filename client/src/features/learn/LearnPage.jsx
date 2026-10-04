import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo } from "react"
import { Link, useParams } from "react-router"

import { EmptyState } from "@/components/EmptyState"
import { useCurrentLearner } from "@/lib/learner"
import { keys } from "@/lib/queries"
import { clearCurrentSession, setCurrentSession } from "@/lib/session"

import { buildCases } from "./caseModel"
import { CaseRail } from "./CaseRail"
import { CaseView, PastCase } from "./CaseView"
import { SummaryView } from "./SummaryView"
import { useThread } from "./useThread"

export function LearnPage() {
  const { sessionId } = useParams()
  // Keyed so a different session starts with fresh thread state.
  return <LearnSession key={sessionId} sessionId={Number(sessionId)} />
}

function LearnSession({ sessionId }) {
  const thread = useThread(sessionId)
  const learner = useCurrentLearner()
  const queryClient = useQueryClient()
  const { cases, summary } = useMemo(() => buildCases(thread.steps), [thread.steps])
  const progress = useMemo(() => thread.steps.findLast((s) => s.progress)?.progress ?? null, [thread.steps])

  // This session is the open one while it runs, and stops being open the moment
  // it reaches its summary. Opening a session by its URL counts as opening it.
  useEffect(() => {
    if (!learner) return
    if (summary) {
      clearCurrentSession(sessionId)
      queryClient.invalidateQueries({ queryKey: keys.learners })
    } else if (!thread.loading && !thread.loadError) {
      setCurrentSession({ id: sessionId, learnerId: learner.id })
    }
  }, [summary, sessionId, learner, thread.loading, thread.loadError, queryClient])

  if (thread.loading) return <LearnSkeleton />
  if (thread.loadError) {
    return (
      <div className="px-6 py-20">
        <EmptyState
          eyebrow="Session"
          title="This session can't be opened"
          action={
            <Link to="/" className="font-medium text-accent underline underline-offset-4">
              Start a new session
            </Link>
          }
        >
          <p>{thread.loadError.message}</p>
        </EmptyState>
      </div>
    )
  }

  const current = summary ? null : cases.at(-1)
  const past = summary ? cases : cases.slice(0, -1)

  return (
    <div className="mx-auto grid max-w-[1240px] gap-8 px-6 py-8 lg:grid-cols-[232px_minmax(0,1fr)] lg:gap-12 lg:px-10 lg:py-10">
      <CaseRail c={current} progress={progress} learner={learner} summary={summary} />
      <div className="min-w-0 max-w-[880px] space-y-3" aria-live="polite">
        {past.map((c) => (
          <PastCase key={c.number} c={c} />
        ))}
        {current && <CaseView key={current.number} c={current} live thread={thread} />}
        {summary && <SummaryView summary={summary} cases={cases} learner={learner} />}
      </div>
    </div>
  )
}

function LearnSkeleton() {
  return (
    <div className="mx-auto grid max-w-[1240px] gap-12 px-6 py-10 lg:grid-cols-[232px_minmax(0,1fr)] lg:px-10" aria-busy="true">
      <div className="hidden space-y-3 lg:block">
        <div className="h-4 w-32 animate-pulse rounded bg-surface-2" />
        <div className="h-8 w-24 animate-pulse rounded bg-surface-2" />
      </div>
      <div className="h-[420px] max-w-[880px] animate-pulse rounded-panel bg-surface-2/70" />
    </div>
  )
}
