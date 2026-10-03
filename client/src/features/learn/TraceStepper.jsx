import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw } from "lucide-react"
import { AnimatePresence, motion } from "motion/react"
import { useEffect, useId, useState } from "react"

import { CodeBlock } from "@/components/CodeBlock"
import { ProvenanceTag } from "@/components/ProvenanceTag"
import { cn } from "@/lib/cn"
import { ease } from "@/lib/motion"

const PLAY_MS = 900

/**
 * Steps through a real execution of the program (recorded by the backend
 * with sys.settrace, never by the LLM): the line about to run, the variables
 * at that moment, and everything printed so far.
 * Keys: ← → to step, space to play/pause, Home/End to jump.
 */
export function TraceStepper({ trace }) {
  const steps = trace.steps
  const last = steps.length - 1
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)

  // Stop at the end of the run (adjusting state during render, not in an effect).
  if (playing && index >= last) setPlaying(false)

  useEffect(() => {
    if (!playing) return
    const timer = setInterval(() => setIndex((i) => Math.min(i + 1, last)), PLAY_MS)
    return () => clearInterval(timer)
  }, [playing, last])

  const go = (i) => {
    setPlaying(false)
    setIndex(Math.max(0, Math.min(last, i)))
  }

  const onKeyDown = (event) => {
    const map = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: last }
    if (event.key in map) {
      event.preventDefault()
      go(map[event.key])
    } else if (event.key === " ") {
      event.preventDefault()
      togglePlay()
    }
  }

  const togglePlay = () => {
    if (index >= last) {
      setIndex(0)
      setPlaying(true)
    } else setPlaying((p) => !p)
  }

  const step = steps[index]
  const previous = index > 0 ? steps[index - 1] : null
  const finished = index === last && step.end
  const atDivergence = trace.divergence_line != null && step.line === trace.divergence_line
  const output = step.stdout ? step.stdout.split("\n") : []

  return (
    <div
      tabIndex={0}
      onKeyDown={onKeyDown}
      aria-label="Execution trace. Use the left and right arrow keys to step."
      className="space-y-4 rounded-panel outline-none focus-visible:ring-4 focus-visible:ring-accent/20"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-small font-medium text-muted">Step through the real run</span>
        <ProvenanceTag kind="exec" label="Recorded by running it" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <CodeBlock
          code={trace.program}
          activeLine={finished ? null : step.line}
          markLine={trace.divergence_line}
          note={trace.divergence_note}
        />

        <div className="space-y-4">
          <div className="overflow-hidden rounded-panel border border-rule">
            <div className="flex h-9 items-center justify-between border-b border-rule bg-surface-2/60 px-4 text-small text-muted">
              <span>Variables</span>
              <span className="font-mono text-[13px]">{finished ? "finished" : `before line ${step.line}`}</span>
            </div>
            <VariableTable locals={step.locals} previous={previous?.locals} />
          </div>

          <div className="overflow-hidden rounded-panel border border-rule">
            <div className="flex h-9 items-center border-b border-rule bg-surface-2/60 px-4 text-small text-muted">
              Printed so far
            </div>
            <pre className="min-h-[3.25rem] px-4 py-2.5 font-mono text-code text-ink">
              <AnimatePresence initial={false}>
                {output.length === 0 ? (
                  <motion.span key="nothing" className="font-sans text-small italic text-muted" exit={{ opacity: 0 }}>
                    nothing yet
                  </motion.span>
                ) : (
                  output.map((line, i) => (
                    <motion.div
                      key={`${i}:${line}`}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.25, ease }}
                    >
                      {line || " "}
                    </motion.div>
                  ))
                )}
              </AnimatePresence>
            </pre>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1">
          <IconButton label="Previous step" onClick={() => go(index - 1)} disabled={index === 0}>
            <ChevronLeft className="size-5" strokeWidth={1.75} />
          </IconButton>
          <IconButton label={playing ? "Pause" : index >= last ? "Replay" : "Play"} onClick={togglePlay} primary>
            {playing ? (
              <Pause className="size-[18px]" strokeWidth={1.75} />
            ) : index >= last ? (
              <RotateCcw className="size-[18px]" strokeWidth={1.75} />
            ) : (
              <Play className="size-[18px]" strokeWidth={1.75} />
            )}
          </IconButton>
          <IconButton label="Next step" onClick={() => go(index + 1)} disabled={index === last}>
            <ChevronRight className="size-5" strokeWidth={1.75} />
          </IconButton>
        </div>

        <Scrubber steps={steps} index={index} divergence={trace.divergence_line} onPick={go} />

        <span className="ml-auto font-mono text-small tabular text-muted">
          step {index + 1}/{steps.length}
          {atDivergence && !finished && <span className="ml-2 font-sans font-semibold text-improving">· where it diverges</span>}
        </span>
      </div>
    </div>
  )
}

function VariableTable({ locals, previous }) {
  const names = Object.keys(locals)
  if (names.length === 0) {
    return <p className="px-4 py-3 text-small italic text-muted">No variables yet</p>
  }
  return (
    <table className="w-full border-collapse font-mono text-[16px]">
      <tbody>
        {names.map((name) => {
          const value = locals[name]
          const changed = !previous || previous[name] !== value
          return (
            <tr key={name} className="border-b border-rule last:border-0">
              <td className="w-[40%] px-4 py-2 text-ink-2">{name}</td>
              <td className="px-4 py-2">
                <motion.span
                  key={value}
                  initial={changed ? { backgroundColor: "rgba(255, 214, 90, 0.55)" } : false}
                  animate={{ backgroundColor: "rgba(255, 214, 90, 0)" }}
                  transition={{ duration: 1.1, ease }}
                  className="-mx-1 rounded px-1 text-ink"
                >
                  {value}
                </motion.span>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function Scrubber({ steps, index, divergence, onPick }) {
  const thumbId = useId()
  return (
    <div className="flex min-w-[160px] flex-1 items-center gap-[3px]" role="group" aria-label="Jump to a step">
      {steps.map((step, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onPick(i)}
          aria-label={`Step ${i + 1}, line ${step.line}`}
          aria-current={i === index ? "step" : undefined}
          className="group relative flex h-7 flex-1 items-center"
        >
          <span
            className={cn(
              "h-1.5 w-full rounded-full transition-colors",
              i <= index ? "bg-accent" : "bg-surface-2 group-hover:bg-rule-strong",
              divergence != null && step.line === divergence && i > index && "bg-[#f2c14e]/70",
            )}
          />
          {i === index && (
            <motion.span
              layoutId={thumbId}
              className="absolute left-1/2 size-3.5 -translate-x-1/2 rounded-full border-2 border-surface bg-accent shadow-sm"
              transition={{ type: "spring", stiffness: 500, damping: 38 }}
            />
          )}
        </button>
      ))}
    </div>
  )
}

function IconButton({ label, onClick, disabled, primary, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={cn(
        "grid size-9 place-items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-35",
        primary ? "bg-ink text-paper hover:bg-ink-2" : "text-ink-2 hover:bg-surface-2",
      )}
    >
      {children}
    </button>
  )
}
