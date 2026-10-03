/**
 * The only module that talks to the backend. Endpoint shapes are documented
 * in client/API_CONTRACT.md.
 *
 * In development, VITE_SAMPLE_STEPS=1 swaps the HTTP client for a built-in
 * sample backend (src/mocks) so screens the real backend does not serve yet
 * can be built and reviewed. The check below is a compile-time constant, so
 * the production build drops the sample code entirely (scripts/check-dist.mjs
 * verifies this).
 */

export const SAMPLE_MODE = import.meta.env.DEV && import.meta.env.VITE_SAMPLE_STEPS === "1"

export const API_BASE = (import.meta.env.VITE_API_BASE ?? "http://localhost:8000").replace(/\/$/, "")

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }

  /** The backend does not serve this endpoint (yet). */
  get notServed() {
    return this.status === 404 || this.status === 405
  }
}

async function request(path, { method = "GET", body } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(`Can't reach the backend at ${API_BASE}. Is the server running?`, 0)
  }
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
  return response.status === 204 ? null : response.json()
}

async function errorMessage(response) {
  try {
    const body = await response.json()
    if (typeof body.detail === "string") return body.detail
    // FastAPI validation errors arrive as a list of per-field problems.
    if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg).join("; ")
  } catch {
    /* fall through to the status line */
  }
  return `${response.status} ${response.statusText}`
}

const httpApi = {
  health: () => request("/health"),
  topics: () => request("/topics"),
  learners: () => request("/learners"),
  createLearner: (name) => request("/learners", { method: "POST", body: { name } }),
  startSession: (learnerId, topic) =>
    request("/sessions", { method: "POST", body: { learner_id: learnerId, topic } }),
  readSession: (sessionId) => request(`/sessions/${sessionId}`),
  answer: (sessionId, response, reason) =>
    request(`/sessions/${sessionId}/answer`, {
      method: "POST",
      body: { student_response: response, student_explanation: reason },
    }),
  next: (sessionId) => request(`/sessions/${sessionId}/next`, { method: "POST" }),
  history: (learnerId) => request(`/learners/${learnerId}/history`),
  evaluation: () => request("/evaluation"),
}

let resolved = null

function client() {
  if (!resolved) {
    resolved = SAMPLE_MODE
      ? import("../mocks/sampleApi.js").then((module) => module.sampleApi)
      : Promise.resolve(httpApi)
  }
  return resolved
}

/** Call an endpoint through whichever client is active. */
export const api = Object.fromEntries(
  Object.keys(httpApi).map((name) => [name, (...args) => client().then((c) => c[name](...args))]),
)
