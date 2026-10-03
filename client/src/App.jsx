import { useCallback, useEffect, useState } from "react"

import { DiagnoserBadge } from "@/components/DiagnoserBadge"
import { QuizProgress, QuizScreen } from "@/screens/QuizScreen"
import { StartScreen } from "@/screens/StartScreen"
import { api } from "@/api/client"

export default function App() {
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState(null)

  const [learner, setLearner] = useState(null)
  const [step, setStep] = useState(null)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch((cause) => setHealthError(cause.message))
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
    setStep(null)
    setError(null)
  }, [])

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
