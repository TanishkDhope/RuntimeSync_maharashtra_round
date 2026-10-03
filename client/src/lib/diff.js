/**
 * Line-by-line comparison of a student's predicted output with the real one,
 * using the same normalisation as the backend's answer check (trailing
 * whitespace per line and trailing blank lines are ignored).
 */

export function outputLines(text) {
  if (!text) return []
  const lines = text.replace(/\r\n?/g, "\n").split("\n").map((line) => line.trimEnd())
  while (lines.length && lines[lines.length - 1] === "") lines.pop()
  return lines
}

/** Each side as [{text, differs}], where differs means no identical line at the same position. */
export function diffOutputs(student, real) {
  const mine = outputLines(student)
  const theirs = outputLines(real)
  return {
    student: mine.map((text, i) => ({ text, differs: text !== theirs[i] })),
    real: theirs.map((text, i) => ({ text, differs: text !== mine[i] })),
  }
}

export function sameOutput(a, b) {
  return outputLines(a).join("\n") === outputLines(b).join("\n")
}
