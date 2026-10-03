import { useEffect, useState } from "react"
import { Loader2, Play } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { api } from "@/api/client"

const MIXED = "mixed"

/** Pick or create a learner, pick a topic, start a run. No authentication. */
export function StartScreen({ onStart, starting, error }) {
  const [name, setName] = useState("")
  const [topic, setTopic] = useState(MIXED)
  const [topics, setTopics] = useState(null)
  const [learners, setLearners] = useState([])
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.topics(), api.listLearners()])
      .then(([topicRows, learnerRows]) => {
        if (cancelled) return
        setTopics(topicRows)
        setLearners(learnerRows)
      })
      .catch((cause) => {
        if (!cancelled) setLoadError(cause.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const canStart = name.trim().length > 0 && !starting

  function handleSubmit(event) {
    event.preventDefault()
    if (canStart) onStart(name.trim(), topic)
  }

  return (
    <Card className="mx-auto w-full max-w-lg">
      <CardHeader>
        <CardTitle>Start a run</CardTitle>
        <p className="text-sm text-muted-foreground">
          Answer a few Python questions. Each wrong answer is diagnosed against a
          library of known misconceptions.
        </p>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="name">Your name</Label>
            <Input
              id="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Type a name"
              autoFocus
              disabled={starting}
            />
            {learners.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-xs text-muted-foreground">Or continue as</span>
                {learners.map((learner) => (
                  <Button
                    key={learner.id}
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={starting}
                    onClick={() => setName(learner.name)}
                  >
                    {learner.name}
                  </Button>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="topic">Topic</Label>
            <Select value={topic} onValueChange={setTopic} disabled={starting || !topics}>
              <SelectTrigger id="topic" className="w-full">
                <SelectValue placeholder={topics ? "Pick a topic" : "Loading topics…"} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={MIXED}>Mixed — all topics</SelectItem>
                {topics?.map((row) => (
                  <SelectItem key={row.topic} value={row.topic}>
                    {row.topic} ({row.problem_count} problems)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {(error || loadError) && (
            <p className="text-sm text-destructive">{error ?? loadError}</p>
          )}

          <Button type="submit" size="lg" className="w-full" disabled={canStart === false}>
            {starting ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
            {starting ? "Starting…" : "Start"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
