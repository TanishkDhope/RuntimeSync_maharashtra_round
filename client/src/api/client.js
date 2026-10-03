/**
 * The only place that talks to the backend.
 *
 * Every quiz response is a "step" object tagged with a `step` field. The
 * frontend renders whatever step it is handed and holds no flow logic of its
 * own, so new steps (intervention, reassessment) will arrive here without any
 * change to this module.
 */

const BASE = (import.meta.env.VITE_API_BASE ?? "http://localhost:8000").replace(/\/$/, "")

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request(path, { method = "GET", body } = {}) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(
      `Cannot reach the backend at ${BASE}. Is the server running?`,
      0,
    )
  }

  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status)
  }
  return response.status === 204 ? null : response.json()
}

async function errorMessage(response) {
  try {
    const body = await response.json()
    if (typeof body.detail === "string") return body.detail
    // FastAPI validation errors arrive as a list of per-field problems.
    if (Array.isArray(body.detail)) {
      return body.detail.map((item) => item.msg).join("; ")
    }
  } catch {
    /* fall through to the status line */
  }
  return `${response.status} ${response.statusText}`
}

export const api = {
  health: () => request("/health"),
  topics: () => request("/topics"),

  listLearners: () => request("/learners"),
  createLearner: (name) => request("/learners", { method: "POST", body: { name } }),

  startSession: (learnerId, topic) =>
    request("/sessions", { method: "POST", body: { learner_id: learnerId, topic } }),
  readSession: (sessionId) => request(`/sessions/${sessionId}`),
  answer: (sessionId, studentResponse, studentExplanation) =>
    request(`/sessions/${sessionId}/answer`, {
      method: "POST",
      body: {
        student_response: studentResponse,
        student_explanation: studentExplanation,
      },
    }),
  next: (sessionId) => request(`/sessions/${sessionId}/next`, { method: "POST" }),
}

export const API_BASE = BASE
