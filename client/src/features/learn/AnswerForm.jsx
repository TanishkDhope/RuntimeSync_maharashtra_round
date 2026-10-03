import { CornerDownLeft } from "lucide-react"
import { useCallback, useState } from "react"

import { Button } from "@/components/Button"
import { CodeBlock } from "@/components/CodeBlock"
import { CodeEditor } from "@/components/CodeEditor"
import { Label, OutputPad, TextInput } from "@/components/Field"
import { ErrorNote } from "@/components/Notice"

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform)
const SUBMIT_HINT = isMac ? "⌘ ↵" : "Ctrl ↵"

/**
 * One problem and the two required inputs: the answer and a one-line reason.
 * The reason is what the trained model reads, so it is not optional.
 */
export function AnswerForm({ problem, onSubmit, busy, busyLabel, error, submitLabel = "Check my answer", autoFocus }) {
  const [response, setResponse] = useState("")
  const [reason, setReason] = useState("")
  const writeCode = problem.item_type === "write_code"
  const ready = response.trim().length > 0 && reason.trim().length > 0 && !busy

  const submit = useCallback(() => {
    if (ready) onSubmit(response, reason.trim())
  }, [ready, onSubmit, response, reason])

  const onKeyDown = (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      {writeCode ? (
        <div className="space-y-4">
          <p className="max-w-[68ch] text-body text-ink">{problem.problem_text}</p>
          {problem.test_cases?.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-small text-muted">Checked with</span>
              {problem.test_cases.map((test) => (
                <code key={test.call} className="rounded-control bg-surface-2 px-2 py-1 font-mono text-[14.5px] text-ink-2">
                  {test.call}
                </code>
              ))}
            </div>
          )}
          <CodeEditor
            value={response}
            onChange={setResponse}
            disabled={busy}
            onSubmit={submit}
            autoFocus={autoFocus}
            placeholder="def ..."
          />
        </div>
      ) : (
        <div className="space-y-4">
          <CodeBlock code={problem.problem_text} running={busy} />
          <div className="space-y-2">
            <Label htmlFor={`answer-${problem.problem_id}`} hint="exactly as it would appear">
              What does it print?
            </Label>
            <OutputPad
              id={`answer-${problem.problem_id}`}
              value={response}
              onChange={(event) => setResponse(event.target.value)}
              onKeyDown={onKeyDown}
              disabled={busy}
              autoFocus={autoFocus}
              placeholder="Type the output here"
            />
          </div>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor={`reason-${problem.problem_id}`} hint="one line, required">
          Why do you think so?
        </Label>
        <TextInput
          id={`reason-${problem.problem_id}`}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={busy}
          maxLength={300}
          placeholder="In your own words"
          autoComplete="off"
        />
        <p className="text-small text-muted">Your reasoning is what the diagnosis reads, so it matters as much as the answer.</p>
      </div>

      <ErrorNote error={error} />

      <div className="flex flex-wrap items-center gap-4">
        <Button
          type="submit"
          size="lg"
          disabled={!ready && !busy}
          loading={busy}
          hint={busy ? undefined : SUBMIT_HINT}
          icon={<CornerDownLeft className="size-[18px]" strokeWidth={1.75} />}
        >
          {busy ? busyLabel : submitLabel}
        </Button>
      </div>
    </form>
  )
}
