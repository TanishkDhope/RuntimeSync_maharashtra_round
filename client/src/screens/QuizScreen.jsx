import { AskPanel } from "@/components/AskPanel"
import { FeedbackPanel } from "@/components/FeedbackPanel"
import { SummaryPanel } from "@/components/SummaryPanel"

/**
 * Renders whatever step the backend returned. The backend owns the flow, so
 * this switch is the whole of the frontend's knowledge of it. Future steps
 * (intervention, probe, reassessment) become extra cases here.
 */
export function QuizScreen({ step, learnerName, onAnswer, onContinue, onRestart, busy, error }) {
  switch (step.step) {
    case "ask":
      // Keyed by problem so each question gets fresh answer boxes.
      return (
        <AskPanel
          key={step.problem.problem_id}
          step={step}
          onSubmit={onAnswer}
          submitting={busy}
          error={error}
        />
      )

    case "feedback":
      return (
        <FeedbackPanel
          step={step}
          onContinue={onContinue}
          advancing={busy}
          error={error}
        />
      )

    case "summary":
      return <SummaryPanel step={step} learnerName={learnerName} onRestart={onRestart} />

    default:
      return (
        <p className="text-sm text-muted-foreground">
          The backend returned a step this version of the app does not know how to
          render yet: <code>{step.step}</code>
        </p>
      )
  }
}

/** Thin progress strip above the current step. */
export function QuizProgress({ step }) {
  if (step.step === "summary" || !step.progress) return null
  const { index, total } = step.progress
  const done = step.step === "feedback" ? index : index - 1

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          Question {index} of {total}
        </span>
        <span>
          {done} / {total} answered
        </span>
      </div>
      <div className="flex gap-1">
        {Array.from({ length: total }, (_, slot) => (
          <div
            key={slot}
            className={`h-1.5 flex-1 rounded-full ${
              slot < done ? "bg-primary" : slot === index - 1 ? "bg-primary/40" : "bg-muted"
            }`}
          />
        ))}
      </div>
    </div>
  )
}
