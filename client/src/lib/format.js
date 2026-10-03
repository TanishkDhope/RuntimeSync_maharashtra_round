/** Scores are shown exactly as the diagnoser returns them, to two places. */
export function score(value) {
  return value.toFixed(2)
}

export function percent(value, digits = 1) {
  if (value === null || value === undefined) return "—"
  return `${(value * 100).toFixed(digits)}%`
}

export function signedPoints(delta) {
  const points = delta * 100
  return `${points >= 0 ? "+" : "−"}${Math.abs(points).toFixed(1)} pts`
}

export function ordinal(n) {
  const tail = n % 100
  if (tail >= 11 && tail <= 13) return `${n}th`
  return `${n}${["th", "st", "nd", "rd"][n % 10] ?? "th"}`
}

const UNITS = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
]

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" })

export function timeAgo(iso, now = Date.now()) {
  if (!iso) return "—"
  const seconds = (new Date(iso).getTime() - now) / 1000
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit)
  }
  return "just now"
}

export function topicLabel(topic) {
  return topic ? topic.charAt(0).toUpperCase() + topic.slice(1) : "Any topic"
}

/** Multi-line output squeezed onto one line for summaries. */
export function oneLine(text, max = 28) {
  const flat = (text ?? "").replace(/\s*\n\s*/g, " ⏎ ").trim()
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat
}

export function pad2(n) {
  return n.toString().padStart(2, "0")
}
