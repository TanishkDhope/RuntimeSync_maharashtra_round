import { ArrowRight, Check, Loader2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { CodeViewer, OutputBlock } from "@/components/CodeViewer"
import { DiagnosisPanel } from "@/components/DiagnosisPanel"

/** The graded answer, then the diagnosis when the answer was wrong. */
export function FeedbackPanel({ step, onContinue, advancing, error }) {
  const { problem, is_correct: isCorrect } = step
  const isWriteCode = problem.item_type === "write_code"

  return (
    <div className="space-y-4">
      <Card className={isCorrect ? "border-emerald-600/50" : "border-red-600/50"}>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="flex items-center gap-2.5">
            {isCorrect ? (
              <span className="grid size-7 place-items-center rounded-full bg-emerald-600 text-white">
                <Check className="size-4" />
              </span>
            ) : (
              <span className="grid size-7 place-items-center rounded-full bg-red-600 text-white">
                <X className="size-4" />
              </span>
            )}
            <CardTitle className="text-base">
              {isCorrect ? "Correct" : "Not quite"}
            </CardTitle>
          </div>
          <Badge variant="outline" className="shrink-0 font-mono text-xs">
            {problem.problem_id}
          </Badge>
        </CardHeader>

        <CardContent className="space-y-5">
          {isWriteCode ? (
            <>
              <p className="text-[15px] leading-relaxed">{problem.problem_text}</p>
              <div className="space-y-2">
                <Label>Your code</Label>
                <CodeViewer code={step.student_response} />
              </div>
              {step.test_results?.length > 0 && <TestResults results={step.test_results} />}
            </>
          ) : (
            <>
              <CodeViewer code={problem.problem_text} />
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Your answer</Label>
                  <OutputBlock
                    text={step.student_response}
                    tone={isCorrect ? "correct" : "wrong"}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Real output</Label>
                  <OutputBlock text={step.correct_output} tone="correct" />
                </div>
              </div>
            </>
          )}

          <div className="space-y-2">
            <Label>Your reasoning</Label>
            <p className="rounded-md border bg-muted/50 px-3 py-2 text-[15px]">
              {step.student_explanation}
            </p>
          </div>
        </CardContent>
      </Card>

      <DiagnosisPanel
        diagnosis={step.diagnosis}
        diagnoser={step.diagnoser}
        isRealModel={step.diagnoser_is_real_model}
        unknown={step.unknown}
        tied={step.tied}
      />

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button size="lg" onClick={onContinue} disabled={advancing}>
        {advancing ? <Loader2 className="size-4 animate-spin" /> : null}
        {step.has_next ? "Next question" : "See results"}
        {!advancing && <ArrowRight className="size-4" />}
      </Button>
    </div>
  )
}

function TestResults({ results }) {
  const passed = results.filter((row) => row.passed).length

  return (
    <div className="space-y-2">
      <Label>
        Tests — {passed} of {results.length} passed
      </Label>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Call</TableHead>
              <TableHead>Expected</TableHead>
              <TableHead>Got</TableHead>
              <TableHead className="w-16 text-right">Result</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {results.map((row) => (
              <TableRow key={row.call}>
                <TableCell className="font-mono text-sm">{row.call}</TableCell>
                <TableCell className="font-mono text-sm">{row.expected}</TableCell>
                <TableCell className="font-mono text-sm">
                  {row.error ? (
                    <span className="text-red-400">{row.error}</span>
                  ) : (
                    row.got
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {row.passed ? (
                    <Check className="ml-auto size-4 text-emerald-500" />
                  ) : (
                    <X className="ml-auto size-4 text-red-500" />
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function Label({ children }) {
  return <p className="text-sm font-medium text-muted-foreground">{children}</p>
}
