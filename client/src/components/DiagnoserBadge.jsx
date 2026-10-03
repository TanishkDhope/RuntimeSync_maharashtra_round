import { AlertTriangle, Cpu, Database, WifiOff } from "lucide-react"

import { Badge } from "@/components/ui/badge"

/**
 * Says out loud which diagnoser produced the results on screen, so nobody
 * demos the stub by accident.
 */
export function DiagnoserBadge({ health, error }) {
  if (error) {
    return (
      <Badge variant="destructive" className="gap-1.5">
        <WifiOff className="size-3.5" />
        Backend unreachable
      </Badge>
    )
  }
  if (!health) {
    return (
      <Badge variant="outline" className="gap-1.5 text-muted-foreground">
        Checking backend…
      </Badge>
    )
  }

  const isRealModel = health.diagnoser_is_real_model

  return (
    <div className="flex flex-wrap items-center gap-2">
      {isRealModel ? (
        <Badge className="gap-1.5 bg-emerald-600 text-white hover:bg-emerald-600">
          <Cpu className="size-3.5" />
          Trained model
        </Badge>
      ) : (
        <Badge className="gap-1.5 bg-amber-500 text-amber-950 hover:bg-amber-500">
          <AlertTriangle className="size-3.5" />
          Stub diagnoser — not the real model
        </Badge>
      )}
      <Badge variant="outline" className="gap-1.5 font-normal text-muted-foreground">
        <Database className="size-3.5" />
        {health.database}
        {health.database_connected ? "" : " (disconnected)"}
      </Badge>
      <span className="text-xs text-muted-foreground">
        {health.library_size} misconceptions ranked · {health.problem_count} problems
      </span>
    </div>
  )
}
