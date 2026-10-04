import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"

import { api, ApiError } from "@/lib/api"
import { readJson, writeJson } from "@/lib/storage"

/**
 * Every step this session has received, in order: the case thread.
 *
 * The backend only returns the step a session is on, so the full thread is
 * kept per tab in sessionStorage; a refresh restores it, and a fresh tab
 * starts from the backend's current step. The backend owns the flow: this
 * hook only sends answers and "continue", and appends whatever comes back.
 *
 * New mutations: probe (answer to probe question) and retest (answer to each
 * retest question). Both use the same append / resync pattern as answer.
 */
export function useThread(sessionId) {
  const queryClient = useQueryClient()
  const storageKey = `relearn.thread.${sessionId}`
  const [stored] = useState(() => readJson("session", storageKey) ?? [])
  const [appended, setAppended] = useState([])

  const current = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.readSession(sessionId),
    enabled: stored.length === 0,
    staleTime: Infinity,
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  })

  const steps = useMemo(() => {
    const head = stored.length ? stored : current.data ? [current.data] : []
    return head.concat(appended)
  }, [stored, current.data, appended])

  useEffect(() => {
    if (steps.length) writeJson("session", storageKey, steps)
  }, [steps, storageKey])

  const append = (step) => {
    setAppended((list) => [...list, step])
    queryClient.invalidateQueries({ queryKey: ["history"] })
  }

  // A 409 means this tab is out of step with the server: resync to where it is.
  const resync = async (error) => {
    if (error instanceof ApiError && error.status === 409) append(await api.readSession(sessionId))
  }

  const answer = useMutation({
    mutationFn: ({ response, reason }) => api.answer(sessionId, response, reason),
    onSuccess: append,
    onError: resync,
  })

  const advance = useMutation({
    mutationFn: () => api.next(sessionId),
    onSuccess: append,
    onError: resync,
  })

  // Submit answer to the probe question → backend moves to explain state
  const probe = useMutation({
    mutationFn: ({ response, reason }) => api.probe(sessionId, response, reason),
    onSuccess: append,
    onError: resync,
  })

  // Submit answer to a retest question → backend moves to next retest or verdict
  const retest = useMutation({
    mutationFn: ({ response, reason }) => api.retest(sessionId, response, reason),
    onSuccess: append,
    onError: resync,
  })

  return {
    steps,
    loading: steps.length === 0 && current.isPending,
    loadError: steps.length === 0 ? current.error : null,
    answer,
    advance,
    probe,
    retest,
  }
}
