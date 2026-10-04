import { useSyncExternalStore } from "react"

import { readJson, writeJson } from "./storage"

/**
 * The session this browser has open ({id, learnerId}), or null.
 *
 * The backend owns the session; this only remembers which one to offer to
 * resume. It is a store rather than a bare readJson so the header updates the
 * moment a session opens or finishes, instead of whenever it next re-renders.
 */
const KEY = "relearn.session"
const listeners = new Set()
let cache

function read() {
  if (cache === undefined) cache = readJson("local", KEY)
  return cache
}

function publish(value) {
  cache = value
  writeJson("local", KEY, value)
  listeners.forEach((listener) => listener())
}

export function setCurrentSession(session) {
  publish(session)
}

/** Forget the open session. Scoped to an id so a finished session can't clear a newer one. */
export function clearCurrentSession(sessionId) {
  if (sessionId === undefined || read()?.id === sessionId) publish(null)
}

export function useCurrentSession() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    read,
    () => null,
  )
}
