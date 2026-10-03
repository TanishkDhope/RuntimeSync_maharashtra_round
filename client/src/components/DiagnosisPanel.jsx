import { AlertTriangle, Cpu, HelpCircle, Split } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

/**
 * The top candidate misconceptions, each labelled with where it came from.
 *
 * Scores are shown as they arrive. The stub returns coarse, deliberately
 * round numbers; the trained model will return cosine similarities. Nothing
 * here is rescaled or invented.
 *
 * `diagnoser` is the implementation name the backend reported. It goes in the
 * badge tooltip, so the badge text stays short but the active implementation
 * is still inspectable.
 */
export function DiagnosisPanel({ diagnosis, diagnoser, isRealModel, unknown, tied }) {
  if (!diagnosis?.length) return null

  const topScore = diagnosis[0].score
  // Every candidate scoring the same means the ranking carries no information
  // at all. The stub does this on write_code answers, where it has no output
  // to match. Saying that once is clearer than stacking "tied" and "unknown".
  const flat = diagnosis.length > 1 && diagnosis.every((c) => c.score === topScore)

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="text-base">Likely misconception</CardTitle>
          <p className="text-sm text-muted-foreground">
            Ranked against the misconception library
          </p>
        </div>
        {isRealModel ? (
          <Badge
            title={`diagnoser: ${diagnoser}`}
            className="shrink-0 gap-1.5 bg-emerald-600 text-white hover:bg-emerald-600"
          >
            <Cpu className="size-3.5" />
            Trained model
          </Badge>
        ) : (
          <Badge
            title={`diagnoser: ${diagnoser}`}
            className="shrink-0 gap-1.5 bg-amber-500 text-amber-950 hover:bg-amber-500"
          >
            <AlertTriangle className="size-3.5" />
            Stub diagnoser
          </Badge>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {flat ? (
          <Notice
            icon={<HelpCircle className="mt-0.5 size-4 shrink-0" />}
            tone="slate"
            title="Not ranked — these are the beliefs this problem can involve"
            body={
              isRealModel
                ? "The model scored every candidate equally, so this answer does not point at one belief more than another."
                : "The stub diagnoser only works by matching predicted output, so it cannot rank a code answer. The list below is what this problem can involve, not a diagnosis."
            }
          />
        ) : (
          <>
            {tied && (
              <Notice
                icon={<Split className="mt-0.5 size-4 shrink-0" />}
                tone="amber"
                title="Two candidates score the same"
                body="These beliefs predict the same wrong output here, so this answer alone cannot separate them. A follow-up question would be needed to tell them apart."
              />
            )}
            {unknown && (
              <Notice
                icon={<HelpCircle className="mt-0.5 size-4 shrink-0" />}
                tone="slate"
                title="No close match in the library"
                body="Nothing in the library explains this answer well. It may be a careless slip, or a misconception the library does not cover yet."
              />
            )}
          </>
        )}

        <ol className="space-y-3">
          {diagnosis.map((candidate, index) => (
            <li key={candidate.misconception_id} className="space-y-1.5">
              <div className="flex items-start justify-between gap-3">
                <p className="text-[15px] leading-snug">
                  <span className="mr-2 text-muted-foreground">{index + 1}.</span>
                  {candidate.description}
                </p>
                <span className="shrink-0 font-mono text-sm tabular-nums text-muted-foreground">
                  {candidate.score.toFixed(2)}
                </span>
              </div>

              <ScoreBar value={candidate.score} max={Math.max(topScore, 1)} dim={index > 0} />

              <div className="flex flex-wrap items-center gap-2">
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                  {candidate.misconception_id}
                </code>
                {candidate.confusable_group && (
                  <Badge variant="outline" className="text-xs font-normal">
                    confusable: {candidate.confusable_group}
                  </Badge>
                )}
              </div>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

function ScoreBar({ value, max, dim }) {
  const percent = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div
        className={`h-full rounded-full ${dim ? "bg-muted-foreground/40" : "bg-primary"}`}
        style={{ width: `${percent}%` }}
      />
    </div>
  )
}

function Notice({ icon, tone, title, body }) {
  const tones = {
    amber: "border-amber-500/40 bg-amber-500/10 text-amber-200",
    slate: "border-border bg-muted/50 text-foreground",
  }
  return (
    <div className={`flex gap-3 rounded-md border p-3 ${tones[tone]}`}>
      {icon}
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-sm opacity-90">{body}</p>
      </div>
    </div>
  )
}
