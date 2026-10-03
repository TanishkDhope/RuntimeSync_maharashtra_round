/**
 * Turns the list of steps the backend has sent into "cases" for the thread.
 *
 * A case starts with an initial question and runs through
 * answer -> diagnose -> probe -> explain -> retest -> verdict. This module only
 * groups and reads steps; it never decides what comes next. That stays in the
 * backend (brief s9). Step shapes are in client/API_CONTRACT.md.
 */

export const PHASES = ["answer", "diagnose", "probe", "explain", "retest", "verdict"]

export const PHASE_LABEL = {
  answer: "Answer",
  diagnose: "Diagnose",
  probe: "Probe",
  explain: "Explain",
  retest: "Retest",
  verdict: "Verdict",
}

function emptyCase(number, ask = null) {
  return {
    number,
    ask,
    graded: null,
    diagnosis: null,
    correct: null,
    legacy: false,
    probe: null,
    unknown: null,
    intervention: null,
    retest: { items: [], total: null },
    verdict: null,
    hasNext: null,
    last: ask,
  }
}

/** Today's backend sends one "feedback" step; read it in the brief's terms. */
function fromFeedback(step) {
  return {
    graded: {
      problem: step.problem,
      student_response: step.student_response,
      student_explanation: step.student_explanation,
      is_correct: step.is_correct,
      correct_output: step.correct_output ?? null,
      test_results: step.test_results ?? null,
    },
    diagnosis: step.is_correct
      ? null
      : {
          diagnoser: step.diagnoser,
          diagnoser_is_real_model: step.diagnoser_is_real_model,
          candidates: step.diagnosis ?? [],
          probe_gap: step.probe_gap ?? null,
          unknown_threshold: step.unknown_threshold ?? null,
          tied: step.tied,
          unknown: step.unknown,
        },
  }
}

export function buildCases(steps) {
  const cases = []
  let summary = null
  let current = null

  const open = (ask = null) => {
    current = emptyCase(cases.length + 1, ask)
    cases.push(current)
    return current
  }
  const ensure = () => current ?? open()

  for (const step of steps) {
    switch (step.step) {
      case "ask": {
        if (step.phase === "reassess") {
          const c = ensure()
          c.retest.items.push({ ask: step, result: null })
          c.retest.total = step.reassess?.total ?? c.retest.total
          c.last = step
        } else {
          open(step)
        }
        break
      }
      case "feedback": {
        const c = ensure()
        Object.assign(c, fromFeedback(step))
        c.correct = step.is_correct
        c.legacy = true
        c.hasNext = step.has_next
        c.last = step
        break
      }
      case "correct": {
        const c = ensure()
        c.graded = step.graded
        c.correct = true
        c.hasNext = step.has_next
        c.last = step
        break
      }
      case "probe": {
        const c = ensure()
        c.graded = step.graded
        c.diagnosis = step.diagnosis
        c.correct = false
        c.probe = { step, outcome: null }
        c.last = step
        break
      }
      case "unknown": {
        const c = ensure()
        c.graded = step.graded
        c.diagnosis = step.diagnosis
        c.correct = false
        c.unknown = step
        c.hasNext = step.has_next
        c.last = step
        break
      }
      case "intervention": {
        const c = ensure()
        if (step.graded && !c.graded) c.graded = step.graded
        if (step.diagnosis && !c.diagnosis) c.diagnosis = step.diagnosis
        c.correct = false
        if (step.probe_outcome) c.probe = { step: c.probe?.step ?? null, outcome: step.probe_outcome }
        c.intervention = step
        c.last = step
        break
      }
      case "reassess": {
        const c = ensure()
        const item = c.retest.items.at(-1)
        if (item && !item.result) item.result = step
        else c.retest.items.push({ ask: null, result: step })
        c.retest.total = step.total
        c.last = step
        break
      }
      case "result": {
        const c = ensure()
        c.verdict = step
        c.hasNext = step.has_next
        c.last = step
        break
      }
      case "summary":
        summary = step
        current = null
        break
      default:
        break
    }
  }
  return { cases, summary }
}

/** The problem a case is about, whichever step introduced it. */
export function caseProblem(c) {
  return c.ask?.problem ?? c.graded?.problem ?? null
}

/** Reads a diagnosis: the gap between the top two, and whether it is close, flat or unknown. */
export function readDiagnosis(d) {
  const candidates = d?.candidates ?? []
  const [top, second] = candidates
  const gap = top && second ? top.score - second.score : null
  const flat = candidates.length > 1 && candidates.every((c) => c.score === top.score)
  const closeCall =
    !flat &&
    gap !== null &&
    (d.tied === true || (d.probe_gap !== null && d.probe_gap !== undefined && gap < d.probe_gap))
  const unknown =
    d?.unknown ??
    (top && d.unknown_threshold !== null && d.unknown_threshold !== undefined
      ? top.score < d.unknown_threshold
      : false)
  return { candidates, top, second, gap, flat, closeCall, unknown: Boolean(unknown) }
}

/** Which phase the learner is looking at right now. */
export function focusPhase(c) {
  switch (c.last?.step) {
    case "ask":
      return c.last.phase === "reassess" ? "retest" : "answer"
    case "feedback":
      return c.correct ? "answer" : "diagnose"
    case "correct":
      return "answer"
    case "probe":
      return "probe"
    case "unknown":
      return "diagnose"
    case "intervention":
      return "explain"
    case "reassess":
      return "retest"
    case "result":
      return "verdict"
    default:
      return "answer"
  }
}

const NOT_SERVED = { state: "unavailable", note: "Not served by the backend yet" }

/**
 * Display state of every phase in a case: done, current, upcoming, skipped
 * (with the reason) or unavailable (the backend doesn't serve it yet).
 * Showing skipped phases and why is what makes the adaptive flow visible.
 */
export function phaseStates(c) {
  const focus = focusPhase(c)
  const d = c.diagnosis ? readDiagnosis(c.diagnosis) : null
  const graded = Boolean(c.graded)
  const afterCorrect = { state: "skipped", note: "Answer was correct" }
  const afterUnknown = { state: "skipped", note: "No belief in the library fits" }

  const states = {}

  states.answer = graded ? { state: "done" } : { state: "current" }

  if (!graded) states.diagnose = { state: "upcoming" }
  else if (c.correct) states.diagnose = afterCorrect
  else states.diagnose = { state: "done" }

  if (c.probe?.outcome) states.probe = { state: "done" }
  else if (c.probe) states.probe = { state: "current" }
  else if (!graded) states.probe = { state: "upcoming" }
  else if (c.correct) states.probe = afterCorrect
  else if (c.unknown) states.probe = afterUnknown
  else if (c.intervention && d) {
    states.probe = {
      state: "skipped",
      note:
        d.gap !== null && c.diagnosis.probe_gap != null
          ? `Gap ${d.gap.toFixed(2)} ≥ ${c.diagnosis.probe_gap.toFixed(2)}`
          : "Clear winner",
    }
  } else if (c.legacy) states.probe = NOT_SERVED
  else states.probe = { state: "upcoming" }

  const later = (done, active) => {
    if (done) return { state: "done" }
    if (active) return { state: "current" }
    if (!graded) return { state: "upcoming" }
    if (c.correct) return afterCorrect
    if (c.unknown) return afterUnknown
    if (c.legacy) return NOT_SERVED
    return { state: "upcoming" }
  }
  states.explain = later(Boolean(c.intervention), false)
  states.retest = later(Boolean(c.verdict), c.retest.items.length > 0)
  states.verdict = later(Boolean(c.verdict), false)

  // The phase on screen is "current" even once its step has arrived.
  if (states[focus].state === "done" || states[focus].state === "current") {
    states[focus] = { ...states[focus], focus: true }
  }
  return states
}

/** Label for the continue button, from the step on screen. Presentation only. */
export function continueLabel(c) {
  const last = c.last
  switch (last?.step) {
    case "feedback":
    case "correct":
    case "unknown":
    case "result":
      return c.hasNext ? "Next problem" : "See the session summary"
    case "intervention":
      return "Start the retest"
    case "reassess":
      return last.index < last.total ? "Next check" : "See the verdict"
    default:
      return "Continue"
  }
}

/** What the learner is waiting for while a request runs. */
export function busyLabel(c, action) {
  if (action === "answer") {
    if (c.last?.step === "probe") return "Checking which belief your answer matches…"
    const problem = c.last?.problem ?? caseProblem(c)
    return problem?.item_type === "write_code"
      ? "Running your code in a sandbox (5 s limit)…"
      : "Checking your answer…"
  }
  if (c.last?.step === "reassess" && c.last.index >= c.last.total) return "Weighing the evidence…"
  return "Loading…"
}

/** Whether the step on screen takes an answer (rather than a continue). */
export function takesAnswer(c) {
  return c.last?.step === "ask" || (c.last?.step === "probe" && !c.probe?.outcome)
}
