import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { useEffect, useState } from "react"

import { CodeBlock } from "@/components/CodeBlock"
import { ease } from "@/lib/motion"

const PROGRAM = "for i in range(3):\n    print(i)"
const STUDENT = ["1", "2", "3"]
const REAL = ["0", "1", "2"]
const BELIEF = "Believes range(n) counts from 1 to n."

// Stage timings (ms). The whole loop is about 7 s; it plays twice, then rests.
const TYPE_MS = 32
const PAUSE = { answer: 450, mark: 900, belief: 1100, hold: 2600 }
const LOOPS = 2

/**
 * The product in one moment: a program, a wrong answer, the wrong lines
 * underlined, and the belief that explains them. Illustrative only, so it is
 * labelled "Example" and not attributed to the model.
 */
export function SignatureDemo() {
  const reduce = useReducedMotion()
  const [state, setState] = useState({ chars: 0, stage: "type", loop: 1 })

  useEffect(() => {
    if (reduce) return
    const { stage, chars, loop } = state
    let timer
    if (stage === "type") {
      timer =
        chars < PROGRAM.length
          ? setTimeout(() => setState((s) => ({ ...s, chars: s.chars + 1 })), TYPE_MS)
          : setTimeout(() => setState((s) => ({ ...s, stage: "answer" })), PAUSE.answer)
    } else if (stage === "answer") {
      timer = setTimeout(() => setState((s) => ({ ...s, stage: "mark" })), PAUSE.mark)
    } else if (stage === "mark") {
      timer = setTimeout(() => setState((s) => ({ ...s, stage: "belief" })), PAUSE.belief)
    } else if (stage === "belief" && loop < LOOPS) {
      timer = setTimeout(() => setState({ chars: 0, stage: "type", loop: loop + 1 }), PAUSE.hold)
    }
    return () => clearTimeout(timer)
  }, [state, reduce])

  const { chars, stage } = reduce ? { chars: PROGRAM.length, stage: "belief" } : state
  const showAnswer = stage !== "type"
  const showMark = stage === "mark" || stage === "belief"
  const showBelief = stage === "belief"

  return (
    <figure className="space-y-4" aria-label="Example: a wrong answer and the belief behind it">
      <div className="flex items-center justify-between">
        <span className="eyebrow">Example</span>
        <span className="text-small text-muted">What does this print?</span>
      </div>

      <CodeBlock code={PROGRAM.slice(0, chars) || " "} className="min-h-[104px]" />

      <div className="grid grid-cols-2 gap-4">
        <MiniOutput label="A student wrote" lines={STUDENT} visible={showAnswer} marked={showMark} />
        <MiniOutput label="Python prints" lines={REAL} visible={showAnswer} real />
      </div>

      <div className="relative min-h-[92px]">
        <AnimatePresence>
          {showBelief && (
            <motion.blockquote
              key="belief"
              initial={{ opacity: 0, y: 10, filter: "blur(6px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, transition: { duration: 0.2 } }}
              transition={{ duration: 0.7, ease }}
              className="border-l-[3px] border-accent pl-5"
            >
              <p className="font-serif text-belief italic text-ink">“{BELIEF}”</p>
              <footer className="mt-1.5 text-small text-muted">The belief behind the answer, not just the mistake.</footer>
            </motion.blockquote>
          )}
        </AnimatePresence>
      </div>
    </figure>
  )
}

function MiniOutput({ label, lines, visible, marked = false, real = false }) {
  return (
    <div className="space-y-1.5">
      <span className="text-small font-medium text-muted">{label}</span>
      <div
        className={
          real
            ? "min-h-[108px] rounded-panel border border-exec/25 bg-exec-soft/40 px-4 py-2.5"
            : "min-h-[108px] rounded-panel border border-rule-strong bg-surface px-4 py-2.5"
        }
      >
        <AnimatePresence>
          {visible &&
            lines.map((line, index) => (
              <motion.div
                key={line + index}
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25, delay: index * 0.09, ease }}
                className="relative w-max font-mono text-code"
              >
                {line}
                {marked && (
                  <motion.span
                    aria-hidden="true"
                    className="absolute -bottom-0.5 left-0 h-[2.5px] w-full origin-left rounded-full bg-active"
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ duration: 0.4, delay: index * 0.12, ease }}
                  />
                )}
              </motion.div>
            ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
