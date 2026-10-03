import { lazy, Suspense, useState } from "react"
import { Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { CodeViewer } from "@/components/CodeViewer"

// CodeMirror is most of the bundle and is only needed for write_code
// items, which SERVE_WRITE_CODE turns off by default. Loading it on
// demand keeps the predict_output path - the whole demo - light.
const CodeEditor = lazy(async () => ({
  default: (await import("@/components/CodeEditor")).CodeEditor,
}))

/**
 * One problem, the answer box, and the required one-line reason.
 *
 * The reason is not optional: it is what the trained diagnoser will rank
 * misconceptions against, so an answer without it is not diagnosable.
 */
export function AskPanel({ step, onSubmit, submitting, error }) {
  const { problem, progress } = step
  const isWriteCode = problem.item_type === "write_code"

  // A fresh problem means a fresh answer. QuizScreen keys this component by
  // problem_id, so a new problem remounts it and both boxes start empty.
  const [response, setResponse] = useState("")
  const [reason, setReason] = useState("")

  const canSubmit = response.trim().length > 0 && reason.trim().length > 0 && !submitting

  function handleSubmit(event) {
    event.preventDefault()
    if (canSubmit) onSubmit(response, reason.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1">
            <CardTitle className="text-base">
              {isWriteCode ? "Write the code" : "What does this print?"}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Question {progress.index} of {progress.total}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap justify-end gap-2">
            <Badge variant="secondary">{problem.topic}</Badge>
            <Badge variant="outline" className="font-mono text-xs">
              {problem.problem_id}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="space-y-5">
          {isWriteCode ? (
            <>
              <p className="text-[15px] leading-relaxed">{problem.problem_text}</p>
              {problem.test_cases?.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-sm font-medium text-muted-foreground">
                    It will be tested with
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {problem.test_cases.map((testCase) => (
                      <li
                        key={testCase.call}
                        className="rounded border bg-muted/50 px-2 py-1 font-mono text-sm"
                      >
                        {testCase.call}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="space-y-2">
                <Label>Your code</Label>
                <Suspense
                  fallback={
                    <div className="flex h-[240px] items-center justify-center rounded-md border text-sm text-muted-foreground">
                      Loading the editor...
                    </div>
                  }
                >
                  <CodeEditor value={response} onChange={setResponse} disabled={submitting} />
                </Suspense>
              </div>
            </>
          ) : (
            <>
              <CodeViewer code={problem.problem_text} />
              <div className="space-y-2">
                <Label htmlFor="answer">The output</Label>
                <Textarea
                  id="answer"
                  value={response}
                  onChange={(event) => setResponse(event.target.value)}
                  disabled={submitting}
                  rows={4}
                  spellCheck={false}
                  placeholder="Type exactly what the program prints, one line per printed line"
                  className="font-mono text-[15px]"
                />
              </div>
            </>
          )}

          <div className="space-y-2">
            <Label htmlFor="reason">
              Why? <span className="font-normal text-muted-foreground">(one line, required)</span>
            </Label>
            <Input
              id="reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              disabled={submitting}
              placeholder="In your own words, why does it do that?"
            />
            <p className="text-xs text-muted-foreground">
              Your reasoning is what the diagnosis is based on, so an answer without it
              cannot be diagnosed.
            </p>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button type="submit" size="lg" disabled={!canSubmit}>
            {submitting && <Loader2 className="size-4 animate-spin" />}
            {submitting
              ? isWriteCode
                ? "Running your code…"
                : "Checking…"
              : "Submit answer"}
          </Button>
        </CardContent>
      </Card>
    </form>
  )
}
