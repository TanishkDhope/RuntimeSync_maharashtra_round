import { Check, RotateCcw, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

/** End of the run: the score, and which beliefs came up. */
export function SummaryPanel({ step, learnerName, onRestart }) {
  const { correct_count: correct, total, misconception_counts: counts } = step

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {learnerName}: {correct} of {total} correct
          </CardTitle>
          <p className="text-sm text-muted-foreground">Topic: {step.topic}</p>
        </CardHeader>
        <CardContent className="space-y-2">
          {step.attempts.map((attempt, index) => (
            <div
              key={`${attempt.problem_id}-${index}`}
              className="flex items-center justify-between gap-3 rounded-md border px-3 py-2"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                {attempt.is_correct ? (
                  <Check className="size-4 shrink-0 text-emerald-500" />
                ) : (
                  <X className="size-4 shrink-0 text-red-500" />
                )}
                <code className="shrink-0 text-sm">{attempt.problem_id}</code>
                <Badge variant="secondary" className="shrink-0 text-xs font-normal">
                  {attempt.item_type === "write_code" ? "write code" : "predict output"}
                </Badge>
              </div>
              {attempt.top_misconception ? (
                <code className="truncate text-xs text-muted-foreground">
                  {attempt.top_misconception}
                </code>
              ) : attempt.is_correct ? null : (
                <span className="shrink-0 text-xs italic text-muted-foreground">
                  not narrowed down
                </span>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {(counts.length > 0 || step.undiagnosed_count > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Beliefs that came up</CardTitle>
            <p className="text-sm text-muted-foreground">
              Counted only where the diagnoser put one belief ahead of the rest.
              {step.undiagnosed_count > 0 && (
                <>
                  {" "}
                  {step.undiagnosed_count} wrong{" "}
                  {step.undiagnosed_count === 1 ? "answer was" : "answers were"} not
                  narrowed to a single belief, so {step.undiagnosed_count === 1 ? "it is" : "they are"}{" "}
                  not counted here.
                </>
              )}
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {counts.map((item) => (
              <div key={item.misconception_id} className="space-y-1">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-[15px] leading-snug">{item.description}</p>
                  <Badge variant="secondary" className="shrink-0">
                    {item.times}×
                  </Badge>
                </div>
                <code className="text-xs text-muted-foreground">
                  {item.misconception_id}
                </code>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Button size="lg" variant="outline" onClick={onRestart}>
        <RotateCcw className="size-4" />
        Start another run
      </Button>
    </div>
  )
}
