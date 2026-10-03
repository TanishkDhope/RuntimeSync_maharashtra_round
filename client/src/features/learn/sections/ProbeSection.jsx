import { CornerDownLeft } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/Button"
import { CodeBlock } from "@/components/CodeBlock"
import { Label, OutputPad } from "@/components/Field"
import { ErrorNote, Notice } from "@/components/Notice"
import { Section } from "@/components/Section"

import { PhaseMark } from "../parts"

/** A normal-looking follow-up question; internal candidates stay server-side. */
export function ProbeSection({ c, folded, interactive, form }) {
  const [response, setResponse] = useState("")
  const probe = c.probe.step?.probe
  const outcome = c.probe.outcome
  const ready = response.trim() && !form?.busy

  return (
    <Section
      index={3}
      phase="Probe"
      status={<PhaseMark state={outcome ? "done" : "current"} />}
      title="Diagnostic Probe"
      summary={outcome ? "Additional evidence recorded" : "One more example to test your reasoning"}
      folded={folded}
    >
      {outcome ? (
        <Notice title="Probe complete">{outcome.display_message}</Notice>
      ) : probe && (
        <div className="space-y-5">
          <p className="max-w-[64ch] text-body text-ink">Work out what this small program prints. This helps us understand your reasoning.</p>
          <CodeBlock code={probe.problem_text} running={form?.busy} />
          {interactive ? (
            <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (ready) form.onSubmit(response) }}>
              <div className="space-y-2">
                <Label htmlFor={`probe-${probe.id}`} hint="exactly as it would appear">What does it print?</Label>
                <OutputPad id={`probe-${probe.id}`} value={response} onChange={(event) => setResponse(event.target.value)} disabled={form.busy} autoFocus placeholder="Type the output here" />
              </div>
              <ErrorNote error={form.error} />
              <Button type="submit" size="lg" disabled={!ready} loading={form.busy} icon={<CornerDownLeft className="size-[18px]" />}>
                {form.busy ? form.busyLabel : "Submit probe answer"}
              </Button>
            </form>
          ) : <CodeBlock code={probe.problem_text} />}
        </div>
      )}
    </Section>
  )
}
