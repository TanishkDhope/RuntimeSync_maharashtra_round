import { useQuery } from "@tanstack/react-query"

import { api, ApiError } from "./api"

export const keys = {
  health: ["health"],
  topics: ["topics"],
  learners: ["learners"],
  history: (learnerId) => ["history", learnerId],
  evidence: (learnerId, misconceptionId) => ["evidence", learnerId, misconceptionId],
  evaluation: ["evaluation"],
}

/** Don't retry an endpoint the backend simply doesn't serve. */
function retry(failureCount, error) {
  if (error instanceof ApiError && (error.notServed || error.status === 422)) return false
  return failureCount < 2
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: api.health, retry, refetchInterval: 30_000 })
}

export function useTopics() {
  return useQuery({ queryKey: keys.topics, queryFn: api.topics, retry, staleTime: Infinity })
}

export function useLearners() {
  return useQuery({ queryKey: keys.learners, queryFn: api.learners, retry })
}

export function useHistory(learnerId) {
  return useQuery({
    queryKey: keys.history(learnerId),
    queryFn: () => api.history(learnerId),
    retry,
    enabled: Number.isFinite(learnerId),
  })
}

/** The trail behind one belief's status. Only fetched when a row is opened. */
export function useBeliefEvidence(learnerId, misconceptionId, enabled) {
  return useQuery({
    queryKey: keys.evidence(learnerId, misconceptionId),
    queryFn: () => api.beliefEvidence(learnerId, misconceptionId),
    retry,
    enabled: Boolean(enabled) && Number.isFinite(learnerId) && Boolean(misconceptionId),
  })
}

export function useEvaluation() {
  return useQuery({ queryKey: keys.evaluation, queryFn: api.evaluation, retry })
}

export function isNotServed(error) {
  return error instanceof ApiError && error.notServed
}
