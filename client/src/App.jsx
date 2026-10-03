import { useCallback, useEffect, useState } from "react"

import { DiagnoserBadge } from "@/components/DiagnoserBadge"
import { QuizProgress, QuizScreen } from "@/screens/QuizScreen"
import { StartScreen } from "@/screens/StartScreen"
import { api, ApiError } from "@/api/client"

/**
 * Where the in-progress session is remembered across a page reload.
 *
 * The backend owns the flow, so resuming is just asking it which step the
 * session is sitting on. All that has to survive the reload is the session id
 * and who was answering.
 */
const RESUME_KEY = "relearn.session"

function readResume() {
  try {
    const raw = window.localStorage.getItem(RESUME_KEY)
    if (!raw) return null
    const saved = JSON.parse(raw)
    return typeof saved?.sessionId === "number" ? saved : null
  } catch {
    // A private window, or a half-written value from an older build.
    return null
  }
}

function writeResume(value) {
  try {
    if (value === null) window.localStorage.removeItem(RESUME_KEY)
    else window.localStorage.setItem(RESUME_KEY, JSON.stringify(value))
  } catch {
    // Not being able to remember is not worth breaking the page over.
  }
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState(null)

  const [learner, setLearner] = useState(null)
  const [step, setStep] = useState(null)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // Blocks the start screen for the one moment it takes to ask the backend
  // whether the remembered session is still there, so a reload mid-quiz does
  // not flash the start screen first.
  const [resuming, setResuming] = useState(() => readResume() !== null)

  useEffect(() => {
    api.health().then(setHealth).catch((cause) => setHealthError(cause.message))
  }, [])

  useEffect(() => {
    const saved = readResume()
    if (!saved) return

    let cancelled = false
    api
      .readSession(saved.sessionId)
      .then((current) => {
        if (cancelled) return
        setLearner({ id: saved.learnerId, name: saved.learnerName })
        setStep(current)
      })
      .catch((cause) => {
        if (cancelled) return
        // A session from a database that has since been rebuilt. Forget it
        // and start over rather than showing an error nobody can act on.
        if (cause instanceof ApiError && cause.status === 404) writeResume(null)
        else setError(cause.message)
      })
      .finally(() => {
        if (!cancelled) setResuming(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  /** Wraps a backend call with the shared busy and error handling. */
  const run = useCallback(async (work) => {
    setBusy(true)
    setError(null)
    try {
      return await work()
    } catch (cause) {
      setError(cause.message)
      return null
    } finally {
      setBusy(false)
    }
  }, [])

  const handleStart = useCallback(
    (name, topic) =>
      run(async () => {
        const created = await api.createLearner(name)
        const first = await api.startSession(created.id, topic)
        setLearner(created)
        setStep(first)
        writeResume({
          sessionId: first.session_id,
          learnerId: created.id,
          learnerName: created.name,
        })
      }),
    [run],
  )

  const handleAnswer = useCallback(
    (response, reason) =>
      run(async () => {
        setStep(await api.answer(step.session_id, response, reason))
      }),
    [run, step],
  )

  const handleContinue = useCallback(
    () =>
      run(async () => {
        setStep(await api.next(step.session_id))
      }),
    [run, step],
  )

  const handleRestart = useCallback(() => {
    writeResume(null)
    setStep(null)
    setError(null)
  }, [])

  if (resuming) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        Picking up where you left off...
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <div className="flex items-baseline gap-3">
            <h1 className="text-xl font-semibold tracking-tight">Re:Learn</h1>
            <p className="text-sm text-muted-foreground">Python misconception diagnosis</p>
          </div>
          <DiagnoserBadge health={health} error={healthError} />
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-4 px-6 py-8">
        {step === null ? (
          <StartScreen onStart={handleStart} starting={busy} error={error} />
        ) : (
          <>
            <QuizProgress step={step} />
            <QuizScreen
              step={step}
              learnerName={learner?.name ?? ""}
              onAnswer={handleAnswer}
              onContinue={handleContinue}
              onRestart={handleRestart}
              busy={busy}
              error={error}
            />
          </>
        )}
      </main>
    </div>
  )
}
