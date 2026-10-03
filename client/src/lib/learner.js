import { useSyncExternalStore } from "react"

import { readJson, writeJson } from "./storage"

/** The learner this browser is working as ({id, name}). No auth: a name is the identity. */
const KEY = "relearn.learner"
const listeners = new Set()
let cache

function read() {
  if (cache === undefined) cache = readJson("local", KEY)
  return cache
}

export function setCurrentLearner(learner) {
  cache = learner
  writeJson("local", KEY, learner)
  listeners.forEach((listener) => listener())
}

export function useCurrentLearner() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    read,
    () => null,
  )
}

export function initials(name) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : name.trim().slice(0, 2)
  return letters.toUpperCase()
}
