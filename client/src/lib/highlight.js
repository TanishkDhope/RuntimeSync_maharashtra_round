import { parser } from "@lezer/python"
import { classHighlighter, highlightCode } from "@lezer/highlight"

const cache = new Map()

/**
 * Python source split into lines of {text, cls} tokens, using the same parser
 * and class names as the CodeMirror editor, so the read-only viewer and the
 * editor colour code identically.
 */
export function highlightLines(source) {
  const code = source.replace(/\r\n?/g, "\n")
  const hit = cache.get(code)
  if (hit) return hit

  const lines = [[]]
  highlightCode(
    code,
    parser.parse(code),
    classHighlighter,
    (text, cls) => lines[lines.length - 1].push({ text, cls }),
    () => lines.push([]),
  )
  cache.set(code, lines)
  return lines
}
