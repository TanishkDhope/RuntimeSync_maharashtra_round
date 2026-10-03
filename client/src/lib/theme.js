import { useCallback, useSyncExternalStore } from "react"

const KEY = "relearn.theme"
const listeners = new Set()

function current() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light"
}

function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setTheme(theme) {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    /* not remembered, still applied */
  }
  listeners.forEach((listener) => listener())
}

/** Light by default (projector); the toggle is remembered per browser. */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, current, () => "light")
  const toggle = useCallback(() => setTheme(theme === "dark" ? "light" : "dark"), [theme])
  return { theme, toggle }
}
