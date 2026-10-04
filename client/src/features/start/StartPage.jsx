import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ArrowRight, CircleCheck, Trash2 } from "lucide-react"
import { motion } from "motion/react"
import { useState } from "react"
import { useNavigate } from "react-router"

import { Button } from "@/components/Button"
import { Label, TextInput } from "@/components/Field"
import { ErrorNote } from "@/components/Notice"
import { api } from "@/lib/api"
import { cn } from "@/lib/cn"
import { initials, setCurrentLearner, useCurrentLearner } from "@/lib/learner"
import { ease, rise, stagger } from "@/lib/motion"
import { keys, useLearners, useTopics } from "@/lib/queries"
import { clearCurrentSession, setCurrentSession, useCurrentSession } from "@/lib/session"
import { writeJson } from "@/lib/storage"
import { timeAgo, topicLabel } from "@/lib/format"

import { SignatureDemo } from "./SignatureDemo"

const MIXED = "mixed"
const SHOWN_LEARNERS = 5

export function StartPage() {
  const learner = useCurrentLearner()

  return (
    <div className="mx-auto grid max-w-[1240px] gap-14 px-6 py-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-20 lg:px-10 lg:py-20">
      <motion.div variants={stagger(0.08)} initial="hidden" animate="shown" className="space-y-10">
        <motion.div variants={rise} className="space-y-5">
          <span className="eyebrow">Python misconception diagnosis</span>
          <h1 className="max-w-[14ch] font-serif text-[44px] font-semibold leading-[1.05] tracking-tight text-ink sm:text-display">
            Find the belief behind the bug.
          </h1>
          <p className="max-w-[56ch] text-body text-ink-2">
            Answer a short Python question and say why. When the answer is wrong, a model we trained ranks the
            beliefs that could have caused it. Re:Learn then teaches against that belief, and retests until it's
            really gone.
          </p>
        </motion.div>
        <motion.div variants={rise}>
          <SignatureDemo />
        </motion.div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15, ease }}
        className="lg:pt-10"
      >
        <StartForm key={learner?.id ?? "nobody"} />
      </motion.div>
    </div>
  )
}

function StartForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const current = useCurrentLearner()
  const localSession = useCurrentSession()
  const learners = useLearners()
  const topics = useTopics()

  const [picked, setPicked] = useState(current?.name ?? null)
  const [typed, setTyped] = useState("")
  const [topic, setTopic] = useState(MIXED)
  const [showAll, setShowAll] = useState(false)
  // Set when someone with an open session asks for a fresh one anyway.
  const [startFresh, setStartFresh] = useState(false)
  // The learner whose delete button was pressed, waiting on the confirm.
  const [pendingDelete, setPendingDelete] = useState(null)

  const name = (typed.trim() || picked || "").trim()
  const typing = Boolean(typed.trim())

  const list = learners.data ?? []
  const pickedLearner = typing ? undefined : list.find((l) => l.name === picked)
  const open = openSessionFor(pickedLearner, localSession)
  const continuing = Boolean(open) && !startFresh

  const start = useMutation({
    mutationFn: async () => {
      const learner = await api.createLearner(name)
      const step = await api.startSession(learner.id, topic)
      return { learner, step }
    },
    onSuccess: ({ learner, step }) => {
      setCurrentLearner({ id: learner.id, name: learner.name })
      setCurrentSession({ id: step.session_id, learnerId: learner.id })
      // The thread starts from this step; LearnPage picks it up from here.
      writeJson("session", `relearn.thread.${step.session_id}`, [step])
      queryClient.invalidateQueries({ queryKey: keys.learners })
      navigate(`/learn/${step.session_id}`)
    },
  })

  const end = useMutation({
    mutationFn: () => api.closeSession(open.id),
    onSuccess: () => {
      // The cached thread stops at whatever step was live; drop it so reopening
      // the session refetches and lands on its summary.
      writeJson("session", `relearn.thread.${open.id}`, null)
      clearCurrentSession(open.id)
      // Drop it from the cached rows too, so the card goes at once rather than
      // lingering on stale data until the refetch lands.
      queryClient.setQueryData(keys.learners, (rows) =>
        rows?.map((row) => (row.open_session?.id === open.id ? { ...row, open_session: null } : row)),
      )
      queryClient.invalidateQueries({ queryKey: keys.learners })
    },
  })

  const removeLearner = useMutation({
    mutationFn: (learner) => api.deleteLearner(learner.id),
    onSuccess: (_result, learner) => {
      // Nobody to be any more: sign out rather than leave the header pointing
      // at a learner the backend no longer has.
      if (current?.id === learner.id) {
        setCurrentLearner(null)
        clearCurrentSession()
      }
      if (picked === learner.name) setPicked(null)
      setPendingDelete(null)
      queryClient.setQueryData(keys.learners, (rows) => rows?.filter((row) => row.id !== learner.id))
      queryClient.invalidateQueries({ queryKey: keys.learners })
      queryClient.invalidateQueries({ queryKey: keys.history(learner.id) })
    },
  })

  const visible = showAll ? list : list.slice(0, SHOWN_LEARNERS)

  /** Picking a different learner re-asks the continue-or-start question. */
  function pick(learner) {
    setPicked(learner.name)
    setTyped("")
    setStartFresh(false)
    end.reset()
    setPendingDelete(null)
    removeLearner.reset()
  }

  function submit(event) {
    event.preventDefault()
    if (!name) return
    if (continuing) {
      // The session may have been opened in another browser, so adopt it here.
      setCurrentLearner({ id: pickedLearner.id, name: pickedLearner.name })
      setCurrentSession({ id: open.id, learnerId: pickedLearner.id })
      navigate(`/learn/${open.id}`)
    } else if (!start.isPending) {
      start.mutate()
    }
  }

  return (
    <form onSubmit={submit} className="space-y-8 rounded-panel border border-rule bg-surface p-7 sm:p-8">
      <div className="space-y-1">
        <h2 className="font-serif text-h2 font-semibold text-ink">
          {continuing ? "Continue session" : "Open a session"}
        </h2>
        <p className="text-[15px] text-muted">
          {continuing
            ? "This session is still open. Pick it up where it stopped, or start a fresh one."
            : "No sign-in. A name is enough, and the same name picks up where it left off."}
        </p>
      </div>

      <fieldset className="space-y-3">
        <legend className="mb-3 text-[15px] font-medium text-ink">Who's learning?</legend>
        {learners.isPending && <SkeletonRows />}
        {learners.isError && <p className="text-small text-active">{learners.error.message}</p>}
        {list.length > 0 && (
          <div role="radiogroup" aria-label="Existing learners" className="overflow-hidden rounded-panel border border-rule">
            {visible.map((learner) => {
              const selected = !typing && picked === learner.name
              const theirs = openSessionFor(learner, localSession)
              return (
                // A div, not a button: the delete control sits inside the row,
                // and a button inside a button is not valid. Enter and Space
                // are wired up by hand to keep the keyboard behaviour.
                <div
                  key={learner.id}
                  role="radio"
                  tabIndex={0}
                  aria-checked={selected}
                  onClick={() => pick(learner)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      pick(learner)
                    }
                  }}
                  className={cn(
                    "flex w-full cursor-pointer items-center gap-3.5 border-b border-rule px-4 py-3 text-left transition-colors last:border-0",
                    selected ? "bg-accent-soft" : "hover:bg-surface-2/70",
                  )}
                >
                  <span
                    className={cn(
                      "grid size-9 shrink-0 place-items-center rounded-full text-small font-semibold",
                      selected ? "bg-accent text-on-accent" : "bg-surface-2 text-ink-2",
                    )}
                  >
                    {initials(learner.name)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px] font-medium text-ink">{learner.name}</span>
                    <span className="block text-small text-muted">{learnerMeta(learner)}</span>
                  </span>
                  {theirs && <InProgressPill />}
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      setPendingDelete(learner)
                      removeLearner.reset()
                    }}
                    title={`Delete ${learner.name}`}
                    aria-label={`Delete ${learner.name}`}
                    className="grid size-7 shrink-0 place-items-center rounded-full text-muted transition-colors hover:bg-active-soft hover:text-active"
                  >
                    <Trash2 className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
                  </button>
                  <span
                    aria-hidden="true"
                    className={cn(
                      "size-4 shrink-0 rounded-full border-2 transition-colors",
                      selected ? "border-accent bg-accent ring-2 ring-inset ring-surface" : "border-rule-strong",
                    )}
                  />
                </div>
              )
            })}
          </div>
        )}
        {pendingDelete && (
          <div className="space-y-3 rounded-panel border border-active/40 bg-paper p-4">
            <p className="text-small text-ink-2">
              Delete <span className="font-semibold text-ink">{pendingDelete.name}</span>? This removes their
              sessions, every answer they gave, and the whole learner model built from them. It cannot be undone.
            </p>
            <ErrorNote error={removeLearner.error} />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="danger"
                loading={removeLearner.isPending}
                onClick={() => removeLearner.mutate(pendingDelete)}
              >
                {removeLearner.isPending ? "Deleting…" : "Delete learner"}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={removeLearner.isPending}
                onClick={() => setPendingDelete(null)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
        {list.length > SHOWN_LEARNERS && (
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="text-small font-medium text-accent underline-offset-4 hover:underline"
          >
            {showAll ? "Show fewer" : `Show all ${list.length} learners`}
          </button>
        )}
        <div className="space-y-2 pt-1">
          <Label htmlFor="new-learner">{list.length ? "Or someone new" : "Your name"}</Label>
          <TextInput
            id="new-learner"
            value={typed}
            onChange={(event) => {
              setTyped(event.target.value)
              setStartFresh(false)
            }}
            placeholder="Type a name"
            autoComplete="off"
            maxLength={80}
          />
        </div>
      </fieldset>

      {continuing ? (
        <OpenSessionCard
          session={open}
          onStartFresh={() => setStartFresh(true)}
          onEnd={() => end.mutate()}
          ending={end.isPending}
          error={end.error}
        />
      ) : (
        <fieldset className="space-y-3">
          <legend className="mb-3 text-[15px] font-medium text-ink">Topic</legend>
          <div className="flex flex-wrap gap-2">
            <TopicChip value={MIXED} label="Mixed" selected={topic === MIXED} onSelect={setTopic} />
            {topics.data?.map((row) => (
              <TopicChip
                key={row.topic}
                value={row.topic}
                label={topicLabel(row.topic)}
                count={row.problem_count}
                selected={topic === row.topic}
                onSelect={setTopic}
              />
            ))}
          </div>
          {topics.isError && <p className="text-small text-active">{topics.error.message}</p>}
          {open && (
            <p className="pt-1 text-small text-muted">
              Starting fresh leaves the open session where it is.{" "}
              <button
                type="button"
                onClick={() => setStartFresh(false)}
                className="font-medium text-accent underline-offset-4 hover:underline"
              >
                Continue it instead
              </button>
            </p>
          )}
        </fieldset>
      )}

      <ErrorNote error={start.error} />

      <Button
        type="submit"
        size="lg"
        className="w-full justify-center"
        disabled={!name}
        loading={start.isPending}
        icon={<ArrowRight className="size-[18px]" strokeWidth={1.75} />}
      >
        {continuing
          ? `Continue session`
          : start.isPending
            ? "Opening…"
            : name
              ? `Start as ${name}`
              : "Start"}
      </Button>
    </form>
  )
}

/**
 * The session a learner has left open, or null.
 *
 * The backend is the authority - it knows about sessions started in any browser
 * - but the sample backend does not report one, so this browser's own memory is
 * the fallback. Only the id is certain in that case.
 */
function openSessionFor(learner, localSession) {
  if (!learner) return null
  if (learner.open_session) return learner.open_session
  if (localSession?.id && localSession.learnerId === learner.id) return { id: localSession.id }
  return null
}

// The open session is called out by the pill beside this line, and described
// in full by the card below once the learner is picked, so it stays out of here.
function learnerMeta(learner) {
  const parts = []
  if (learner.active_count != null) parts.push(`${learner.active_count} active`)
  if (learner.resolved_count != null) parts.push(`${learner.resolved_count} resolved`)
  parts.push(learner.last_seen ? `last seen ${timeAgo(learner.last_seen)}` : `joined ${timeAgo(learner.created_at)}`)
  return parts.join(" · ")
}

function InProgressPill() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-accent/30 bg-accent-soft px-2.5 py-1 text-small font-medium text-accent">
      <span className="size-1.5 rounded-full bg-accent" aria-hidden="true" />
      In progress
    </span>
  )
}

/** What is waiting to be resumed, and the two ways out of resuming it. */
function OpenSessionCard({ session, onStartFresh, onEnd, ending, error }) {
  const [confirming, setConfirming] = useState(false)

  return (
    <div className="space-y-3 rounded-panel border border-accent/30 bg-accent-soft/50 p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="eyebrow text-accent">Open session</span>
        <InProgressPill />
      </div>
      <p className="text-[15px] text-ink">
        {session.topic ? topicLabel(session.topic) : "Mixed"}
        {session.started_at && <span className="text-muted"> · started {timeAgo(session.started_at)}</span>}
      </p>

      {confirming ? (
        <div className="space-y-3 rounded-control border border-rule-strong bg-paper p-3">
          <p className="text-small text-ink-2">
            End this session? It stops showing as in progress. Everything it recorded stays - the attempts, the
            beliefs, the whole path - and it keeps its place in the learner&apos;s history.
          </p>
          <ErrorNote error={error} />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" loading={ending} onClick={onEnd}>
              {ending ? "Ending…" : "End session"}
            </Button>
            <Button type="button" size="sm" variant="ghost" disabled={ending} onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <button
            type="button"
            onClick={onStartFresh}
            className="text-small font-medium text-accent underline-offset-4 hover:underline"
          >
            Start a new session instead
          </button>
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="inline-flex items-center gap-1.5 text-small font-medium text-muted underline-offset-4 hover:text-ink hover:underline"
          >
            <CircleCheck className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
            End session
          </button>
        </div>
      )}
    </div>
  )
}

function TopicChip({ value, label, count, selected, onSelect }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={() => onSelect(value)}
      className={cn(
        "inline-flex h-10 items-center gap-2 rounded-full border px-4 text-[15px] font-medium transition-colors",
        selected
          ? "border-ink bg-ink text-paper"
          : "border-rule-strong bg-surface text-ink-2 hover:border-ink-2/50 hover:text-ink",
      )}
    >
      {label}
      {count != null && <span className={cn("tabular text-small", selected ? "text-paper/70" : "text-muted")}>{count}</span>}
    </button>
  )
}

function SkeletonRows() {
  return (
    <div className="space-y-2" aria-label="Loading learners">
      {[0, 1].map((i) => (
        <div key={i} className="h-14 animate-pulse rounded-panel bg-surface-2/70" />
      ))}
    </div>
  )
}
