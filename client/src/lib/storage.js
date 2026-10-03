/**
 * Small, failure-proof wrappers over Web Storage. Storage can be missing or
 * throw (private windows, blocked site data), so every access is guarded and
 * the app works without it. Only per-viewer conveniences live here.
 */

function store(kind) {
  return kind === "local" ? localStorage : sessionStorage
}

export function readJson(kind, key) {
  try {
    const raw = store(kind).getItem(key)
    return raw === null ? null : JSON.parse(raw)
  } catch {
    return null
  }
}

export function writeJson(kind, key, value) {
  try {
    if (value === null) store(kind).removeItem(key)
    else store(kind).setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable: the app still works, it just won't remember */
  }
}
