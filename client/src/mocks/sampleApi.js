/**
 * DEV-ONLY stand-in backend that speaks the full step contract
 * (client/API_CONTRACT.md), so screens the real backend doesn't serve yet can
 * be built and reviewed. Loaded only when VITE_SAMPLE_STEPS=1 in dev; the
 * production build never contains it. Every score it returns is invented
 * (see fixtures.js), which is why the UI shows a SAMPLE DATA banner.
 */
import { ApiError } from "@/lib/api"
import { sameOutput } from "@/lib/diff"
import { readJson, writeJson } from "@/lib/storage"

import { CASES, EVALUATION, LIBRARY, PROBLEMS, RETEST, TEACHING, TOPICS, TRACES } from "./fixtures"

const KEY = "relearn.sample.state"
const PROBE_GAP = 0.1
const UNKNOWN_THRESHOLD = 0.5

let state = readJson("session", KEY) ?? { nextId: 1, learners: [], sessions: {}, attempts: [], beliefs: {} }
const save = () => writeJson("session", KEY, state)
const now = () => new Date().toISOString()
const id = () => state.nextId++
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms + Math.random() * 250))

// --- shapes -------------------------------------------------------------------

function problemOut(pid) {
  const { problem_id, item_type, topic, problem_text } = PROBLEMS[pid]
  return { problem_id, item_type, topic, problem_text, test_cases: null }
}

function candidate(mid, score) {
  const entry = LIBRARY[mid]
  return { misconception_id: mid, description: entry.description, topic: entry.topic, confusable_group: entry.confusable_group, score }
}

function graded(pid, response, reason) {
  const problem = PROBLEMS[pid]
  return {
    problem: problemOut(pid),
    student_response: response,
    student_explanation: reason,
    is_correct: sameOutput(response, problem.correct_output),
    correct_output: problem.correct_output,
    test_results: null,
  }
}

function diagnosis(pairs) {
  return {
    diagnoser: "model",
    diagnoser_is_real_model: true,
    candidates: pairs.map(([mid, score]) => candidate(mid, score)),
    probe_gap: PROBE_GAP,
    unknown_threshold: UNKNOWN_THRESHOLD,
  }
}

const progress = (s) => ({ index: Math.min(s.caseIndex + 1, CASES.length), total: CASES.length })

function askStep(s, pid, extra = {}) {
  return { step: "ask", session_id: s.id, progress: progress(s), problem: problemOut(pid), phase: "initial", ...extra }
}

function record(s, phase, pid, g, top) {
  state.attempts.push({
    id: id(),
    session_id: s.id,
    learner_id: s.learnerId,
    problem_id: pid,
    topic: PROBLEMS[pid].topic,
    item_type: PROBLEMS[pid].item_type,
    phase,
    is_correct: g.is_correct,
    top_misconception: top,
    created_at: now(),
  })
}

function beliefsOf(learnerId) {
  state.beliefs[learnerId] ??= {}
  return state.beliefs[learnerId]
}

function sessionOr404(sessionId) {
  const s = state.sessions[sessionId]
  if (!s) throw new ApiError(`no session ${sessionId}`, 404)
  return s
}

function finish(s, step) {
  s.last = step
  save()
  return step
}

// --- the flow -----------------------------------------------------------------

function intervention(s, mid, extra = {}) {
  const spec = CASES[s.caseIndex]
  const teach = TEACHING[mid]
  // Confirmed belief: count it, and flip a resolved one back to active.
  const beliefs = beliefsOf(s.learnerId)
  const prior = beliefs[mid]
  s.ctx.misconception = mid
  s.ctx.from = prior?.status ?? null
  beliefs[mid] = {
    misconception_id: mid,
    description: LIBRARY[mid].description,
    topic: LIBRARY[mid].topic,
    status: prior?.status === "resolved" ? "active" : (prior?.status ?? "active"),
    times_seen: (prior?.times_seen ?? 0) + 1,
    last_seen: now(),
    resolved_at: prior?.resolved_at ?? null,
    returned: prior?.status === "resolved" || prior?.returned === true,
  }
  s.phase = "intervention"
  return {
    step: "intervention",
    session_id: s.id,
    progress: progress(s),
    misconception: candidate(mid, s.ctx.diagnosis.candidates.find((c) => c.misconception_id === mid)?.score ?? 0),
    explanation: { text: teach?.text ?? "Step through the run to see where Python differs from your prediction.", source: "authored" },
    trace: {
      program: PROBLEMS[spec.traceOf].problem_text,
      steps: TRACES[spec.traceOf],
      divergence_line: teach?.line ?? null,
      divergence_note: teach?.note ?? null,
    },
    ...extra,
  }
}

function retestAsk(s) {
  const pool = RETEST[CASES[s.caseIndex].retest]
  const item = pool[s.ctx.retestIndex]
  s.phase = "reassess"
  return askStep(s, item.id, {
    phase: "reassess",
    transfer: item.transfer,
    reassess: { index: s.ctx.retestIndex + 1, total: pool.length },
  })
}

function verdict(s) {
  const mid = s.ctx.misconception
  const results = s.ctx.retestResults
  const right = results.filter((r) => r.correct).length
  const rankedFirst = results.some((r) => r.rank === 1)
  const reappeared = results.some((r) => r.predictedHit)
  const outcome = right === results.length && !rankedFirst ? "resolved" : reappeared ? "active" : "improving"

  const belief = beliefsOf(s.learnerId)[mid]
  belief.status = outcome
  belief.last_seen = now()
  if (outcome === "resolved") belief.resolved_at = now()

  s.phase = "result"
  return {
    step: "result",
    session_id: s.id,
    progress: progress(s),
    verdict: outcome,
    reasons: [
      { ok: right === results.length, text: `${right} of ${results.length} retest answers correct` },
      {
        ok: !rankedFirst,
        text: rankedFirst
          ? `The model still ranks ${mid} first on at least one of your reasons`
          : `The model no longer ranks ${mid} first on your reasons`,
      },
      {
        ok: !reappeared,
        text: reappeared
          ? `The wrong output ${mid} predicts came back`
          : `The wrong output ${mid} predicts did not come back`,
      },
    ],
    record: { misconception_id: mid, description: LIBRARY[mid].description, from: s.ctx.from, to: outcome },
    has_next: s.caseIndex < CASES.length - 1,
  }
}

function summary(s) {
  s.phase = "done"
  const attempts = state.attempts.filter((a) => a.session_id === s.id && a.phase === "initial")
  const tally = {}
  attempts.forEach((a) => a.top_misconception && (tally[a.top_misconception] = (tally[a.top_misconception] ?? 0) + 1))
  return {
    step: "summary",
    session_id: s.id,
    topic: s.topic,
    total: CASES.length,
    correct_count: attempts.filter((a) => a.is_correct).length,
    attempts: attempts.map((a) => ({
      problem_id: a.problem_id,
      topic: a.topic,
      item_type: a.item_type,
      is_correct: a.is_correct,
      top_misconception: a.top_misconception,
    })),
    misconception_counts: Object.entries(tally).map(([mid, times]) => ({
      misconception_id: mid,
      description: LIBRARY[mid]?.description ?? mid,
      times,
    })),
    undiagnosed_count: attempts.filter((a) => !a.is_correct && !a.top_misconception).length,
  }
}

function answerInitial(s, response, reason) {
  const spec = CASES[s.caseIndex]
  const g = graded(spec.problem, response, reason)
  s.ctx = { graded: g, retestIndex: 0, retestResults: [] }

  if (g.is_correct) {
    record(s, "initial", spec.problem, g, null)
    s.phase = "answered"
    return { step: "correct", session_id: s.id, progress: progress(s), graded: g, has_next: s.caseIndex < CASES.length - 1 }
  }

  const key = Object.keys(spec.byAnswer).find((answer) => sameOutput(response, answer))
  const match = key ? spec.byAnswer[key] : { ...spec.otherwise, unknown: true }
  const d = diagnosis(match.candidates)
  s.ctx.diagnosis = d

  if (match.unknown) {
    record(s, "initial", spec.problem, g, null)
    s.phase = "answered"
    return {
      step: "unknown",
      session_id: s.id,
      progress: progress(s),
      graded: g,
      diagnosis: d,
      draft: match.draft ? { description: match.draft, source: "llm" } : null,
      has_next: s.caseIndex < CASES.length - 1,
    }
  }

  const [top] = match.candidates
  record(s, "initial", spec.problem, g, top[0])
  if (match.probe) {
    s.phase = "probe"
    s.ctx.probe = match.probe
    return {
      step: "probe",
      session_id: s.id,
      progress: progress(s),
      graded: g,
      diagnosis: d,
      probe: {
        problem: problemOut(match.probe.problem),
        candidates: match.probe.pair,
        source: "bank",
        executed: true,
        independent_check: false,
      },
    }
  }
  return intervention(s, top[0], { graded: g, diagnosis: d })
}

function answerProbe(s, response, reason) {
  const { problem, pair } = s.ctx.probe
  const predictions = Object.fromEntries(pair.map((mid) => [mid, PROBLEMS[problem].predicted_outputs[mid]]))
  const matched = pair.find((mid) => sameOutput(response, predictions[mid])) ?? null
  const g = graded(problem, response, reason)
  record(s, "probe", problem, g, matched)
  return intervention(s, matched ?? pair[0], {
    probe_outcome: { student_response: response, real_output: PROBLEMS[problem].correct_output, predictions, matched },
  })
}

function answerRetest(s, response, reason) {
  const pool = RETEST[CASES[s.caseIndex].retest]
  const pid = pool[s.ctx.retestIndex].id
  const mid = s.ctx.misconception
  const g = graded(pid, response, reason)
  const predictedHit = sameOutput(response, PROBLEMS[pid].predicted_outputs[mid] ?? null)
  const rank = g.is_correct ? 4 : predictedHit ? 1 : 2
  const score = rank === 1 ? 0.76 : rank === 2 ? 0.48 : 0.29
  s.ctx.retestResults.push({ correct: g.is_correct, rank, predictedHit })
  record(s, "reassess", pid, g, rank === 1 ? mid : null)
  s.phase = "reassessed"
  return {
    step: "reassess",
    session_id: s.id,
    progress: progress(s),
    graded: g,
    index: s.ctx.retestIndex + 1,
    total: pool.length,
    model_check: { misconception_id: mid, rank, score },
  }
}

// --- the Api ------------------------------------------------------------------

export const sampleApi = {
  async health() {
    await wait(120)
    return {
      status: "ok",
      diagnoser: "model",
      diagnoser_is_real_model: true,
      model_path: "sample",
      database: "sample",
      database_connected: true,
      problem_count: 135,
      misconception_count: 61,
      library_size: 49,
      llm_configured: true,
      probe_gap: PROBE_GAP,
      unknown_threshold: UNKNOWN_THRESHOLD,
    }
  },

  async topics() {
    await wait(100)
    return TOPICS
  },

  async learners() {
    await wait(150)
    return state.learners.map((learner) => {
      const beliefs = Object.values(state.beliefs[learner.id] ?? {})
      const seen = state.attempts.filter((a) => a.learner_id === learner.id).map((a) => a.created_at)
      return {
        ...learner,
        active_count: beliefs.filter((b) => b.status === "active").length,
        resolved_count: beliefs.filter((b) => b.status === "resolved").length,
        last_seen: seen.at(-1) ?? null,
      }
    })
  },

  async createLearner(name) {
    await wait(150)
    const existing = state.learners.find((l) => l.name === name)
    if (existing) return existing
    const learner = { id: id(), name, created_at: now() }
    state.learners.push(learner)
    save()
    return learner
  },

  async beliefGraph() {
    await wait(120)
    // No belief graph in the sample data: the edges come from the dataset the
    // server loads, which the mock does not have.
    return { nodes: [], edges: [], hidden_beliefs: 0 }
  },

  async beliefEvidence() {
    await wait(120)
    // The sample data has no evidence rows behind it; an empty trail reads
    // the same as a belief nobody has shown yet, which is honest here.
    return []
  },

  async deleteLearner(learnerId) {
    await wait(150)
    const id = Number(learnerId)
    state.learners = state.learners.filter((l) => l.id !== id)
    state.attempts = state.attempts.filter((a) => a.learner_id !== id)
    for (const [key, s] of Object.entries(state.sessions)) {
      if (s.learnerId === id) delete state.sessions[key]
    }
    delete state.beliefs[id]
    save()
    return null
  },

  async startSession(learnerId, topic) {
    await wait(250)
    const s = { id: id(), learnerId, topic, caseIndex: 0, phase: "ask", ctx: {} }
    state.sessions[s.id] = s
    return finish(s, askStep(s, CASES[0].problem))
  },

  async readSession(sessionId) {
    await wait(120)
    return sessionOr404(sessionId).last
  },

  async closeSession(sessionId) {
    await wait(150)
    // Same as running out of cases: the session freezes on its summary and the
    // attempts behind it stay where they are.
    const s = sessionOr404(sessionId)
    return finish(s, summary(s))
  },

  async answer(sessionId, response, reason) {
    const s = sessionOr404(sessionId)
    if (s.phase === "ask") {
      await wait(500)
      return finish(s, answerInitial(s, response, reason))
    }
    if (s.phase === "probe") {
      await wait(1400) // explanation is generated on this hop in the real flow
      return finish(s, answerProbe(s, response, reason))
    }
    if (s.phase === "reassess") {
      await wait(600)
      return finish(s, answerRetest(s, response, reason))
    }
    throw new ApiError("this step doesn't take an answer; continue instead", 409)
  },

  async next(sessionId) {
    const s = sessionOr404(sessionId)
    await wait(400)
    if (s.phase === "answered" || s.phase === "result") {
      s.caseIndex += 1
      if (s.caseIndex >= CASES.length) return finish(s, summary(s))
      s.phase = "ask"
      s.ctx = {}
      return finish(s, askStep(s, CASES[s.caseIndex].problem))
    }
    if (s.phase === "intervention") return finish(s, retestAsk(s))
    if (s.phase === "reassessed") {
      const pool = RETEST[CASES[s.caseIndex].retest]
      s.ctx.retestIndex += 1
      if (s.ctx.retestIndex < pool.length) return finish(s, retestAsk(s))
      return finish(s, verdict(s))
    }
    if (s.phase === "done") return s.last
    throw new ApiError("answer the current question first", 409)
  },

  async probe(sessionId, response, reason) {
    // Sample mode routes probe through the answer endpoint.
    await wait(1400) // explanation generated on this hop
    const s = sessionOr404(sessionId)
    if (s.phase === "probe") return finish(s, answerProbe(s, response, reason))
    return s.last
  },

  async retest(sessionId, response, reason) {
    // Sample mode routes retest through the answer endpoint.
    await wait(600)
    const s = sessionOr404(sessionId)
    if (s.phase === "reassess") return finish(s, answerRetest(s, response, reason))
    return s.last
  },

  async history(learnerId) {
    await wait(250)
    const learner = state.learners.find((l) => l.id === learnerId)
    if (!learner) throw new ApiError(`no learner ${learnerId}`, 404)
    return {
      learner,
      beliefs: Object.values(state.beliefs[learnerId] ?? {}),
      attempts: state.attempts.filter((a) => a.learner_id === learnerId),
    }
  },

  async evaluation() {
    await wait(300)
    return EVALUATION
  },
}
