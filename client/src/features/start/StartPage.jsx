import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ArrowRight } from "lucide-react"
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
import { writeJson } from "@/lib/storage"
import { timeAgo, topicLabel } from "@/lib/format"

import { SignatureDemo } from "./SignatureDemo"

const MIXED = "mixed"
const SHOWN_LEARNERS = 5

export function StartPage() {
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
        <StartForm />
      </motion.div>
    </div>
  )
}

function StartForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const current = useCurrentLearner()
  const learners = useLearners()
  const topics = useTopics()

  const [picked, setPicked] = useState(current?.name ?? null)
  const [typed, setTyped] = useState("")
  const [topic, setTopic] = useState(MIXED)
  const [showAll, setShowAll] = useState(false)

  const name = (typed.trim() || picked || "").trim()

  const start = useMutation({
    mutationFn: async () => {
      const learner = await api.createLearner(name)
      const step = await api.startSession(learner.id, topic)
      return { learner, step }
    },
    onSuccess: ({ learner, step }) => {
      setCurrentLearner({ id: learner.id, name: learner.name })
      writeJson("local", "relearn.session", { id: step.session_id, learnerId: learner.id })
      // The thread starts from this step; LearnPage picks it up from here.
      writeJson("session", `relearn.thread.${step.session_id}`, [step])
      queryClient.invalidateQueries({ queryKey: keys.learners })
      navigate(`/learn/${step.session_id}`)
    },
  })

  const list = learners.data ?? []
  const visible = showAll ? list : list.slice(0, SHOWN_LEARNERS)

  function submit(event) {
    event.preventDefault()
    if (name && !start.isPending) start.mutate()
  }

  return (
    <form onSubmit={submit} className="space-y-8 rounded-panel border border-rule bg-surface p-7 sm:p-8">
      <div className="space-y-1">
        <h2 className="font-serif text-h2 font-semibold text-ink">Open a session</h2>
        <p className="text-[15px] text-muted">No sign-in. A name is enough, and the same name picks up where it left off.</p>
      </div>

      <fieldset className="space-y-3">
        <legend className="mb-3 text-[15px] font-medium text-ink">Who's learning?</legend>
        {learners.isPending && <SkeletonRows />}
        {learners.isError && <p className="text-small text-active">{learners.error.message}</p>}
        {list.length > 0 && (
          <div role="radiogroup" aria-label="Existing learners" className="overflow-hidden rounded-panel border border-rule">
            {visible.map((learner) => {
              const selected = !typed.trim() && picked === learner.name
              return (
                <button
                  key={learner.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => {
                    setPicked(learner.name)
                    setTyped("")
                  }}
                  className={cn(
                    "flex w-full items-center gap-3.5 border-b border-rule px-4 py-3 text-left transition-colors last:border-0",
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
                  <span
                    aria-hidden="true"
                    className={cn(
                      "size-4 shrink-0 rounded-full border-2 transition-colors",
                      selected ? "border-accent bg-accent ring-2 ring-inset ring-surface" : "border-rule-strong",
                    )}
                  />
                </button>
              )
            })}
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
            onChange={(event) => setTyped(event.target.value)}
            placeholder="Type a name"
            autoComplete="off"
            maxLength={80}
          />
        </div>
      </fieldset>

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
      </fieldset>

      <ErrorNote error={start.error} />

      <Button
        type="submit"
        size="lg"
        className="w-full justify-center"
        disabled={!name}
        loading={start.isPending}
        icon={<ArrowRight className="size-[18px]" strokeWidth={1.75} />}
      >
        {start.isPending ? "Opening…" : name ? `Start as ${name}` : "Start"}
      </Button>
    </form>
  )
}

function learnerMeta(learner) {
  const parts = []
  if (learner.active_count != null) parts.push(`${learner.active_count} active`)
  if (learner.resolved_count != null) parts.push(`${learner.resolved_count} resolved`)
  parts.push(learner.last_seen ? `last seen ${timeAgo(learner.last_seen)}` : `joined ${timeAgo(learner.created_at)}`)
  return parts.join(" · ")
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
