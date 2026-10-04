import { motion } from "motion/react"

import { CodeBlock } from "@/components/CodeBlock"
import { ProvenanceTag } from "@/components/ProvenanceTag"
import { Section } from "@/components/Section"
import { cn } from "@/lib/cn"
import { rise } from "@/lib/motion"

import { TraceStepper } from "../TraceStepper"
import { Belief, PhaseMark } from "../parts"

/** 04 · Explain: teaching aimed at the diagnosed belief, plus the real run. */
export function ExplainSection({ c, folded }) {
  const { misconception, explanation, trace } = c.intervention
  const generated = explanation.source === "llm"

  return (
    <Section
      index={4}
      phase="Explain"
      status={<PhaseMark state="done" />}
      title="Where this belief and Python part ways"
      summary={`Explained ${misconception.misconception_id}`}
      folded={folded}
    >
      <div className="space-y-1.5">
        <span className="text-small font-medium text-muted">Addressing the belief</span>
        <Belief size="lg">{misconception.description}</Belief>
        <code className="font-mono text-[13.5px] text-muted">{misconception.misconception_id}</code>
      </div>

      <motion.article
        variants={rise}
        initial="hidden"
        animate="shown"
        className={cn(
          "space-y-4 rounded-panel px-6 py-5",
          generated ? "border border-dashed border-muted/60" : "border border-rule bg-surface-2/40",
        )}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="eyebrow">Explanation</span>
          {generated
            ? <ProvenanceTag kind="llm" label="Generated · Groq" />
            : <ProvenanceTag kind="authored" />
          }
        </div>

        <ExplanationBody text={explanation.text} />
      </motion.article>

      {trace?.steps?.length > 0 && <TraceStepper trace={trace} />}
    </Section>
  )
}

/**
 * Renders LLM-generated explanation text with proper theme formatting.
 *
 * Handles:
 *   - Fenced code blocks (```python … ```) → CodeBlock component
 *   - Paragraph separation by blank lines
 *   - Inline `code` → styled <code> tag
 *   - **bold** → <strong>
 *   - Plain text in the app serif font
 */
function ExplanationBody({ text }) {
  const blocks = parseBlocks(text)

  return (
    <div className="space-y-4">
      {blocks.map((block, i) => {
        if (block.type === "code") {
          return (
            <CodeBlock
              key={i}
              code={block.content}
              label={block.lang === "python" ? "example.py" : undefined}
            />
          )
        }
        // Paragraph block
        return (
          <p
            key={i}
            className="max-w-[64ch] font-serif text-[19px] leading-[1.65] text-ink"
          >
            {renderInline(block.content)}
          </p>
        )
      })}
    </div>
  )
}

/**
 * Split the raw LLM text into an array of blocks:
 *   { type: "paragraph", content: string }
 *   { type: "code", lang: string, content: string }
 */
function parseBlocks(text) {
  const blocks = []
  // Split on fenced code blocks first
  const fenceRe = /```(\w*)\n([\s\S]*?)```/g
  let last = 0
  let match

  while ((match = fenceRe.exec(text)) !== null) {
    // Text before this fence
    const before = text.slice(last, match.index).trim()
    if (before) {
      // Split into paragraphs on blank lines
      for (const para of splitParagraphs(before)) {
        blocks.push({ type: "paragraph", content: para })
      }
    }
    blocks.push({ type: "code", lang: match[1] || "python", content: match[2].trimEnd() })
    last = match.index + match[0].length
  }

  // Remaining text after last fence (or all text if no fences)
  const remaining = text.slice(last).trim()
  if (remaining) {
    for (const para of splitParagraphs(remaining)) {
      blocks.push({ type: "paragraph", content: para })
    }
  }

  return blocks
}

/** Split a plain-text section on blank lines. */
function splitParagraphs(text) {
  return text
    .split(/\n{2,}/)
    .map((s) => s.trim())
    .filter(Boolean)
}

/**
 * Convert a paragraph string to React children, handling:
 *   **bold**   → <strong>
 *   `code`     → <code>
 *   plain text → string
 */
function renderInline(text) {
  // Tokenise on **bold** and `code` patterns
  const parts = []
  const re = /(`[^`]+`|\*\*[^*]+\*\*)/g
  let pos = 0
  let m

  while ((m = re.exec(text)) !== null) {
    if (m.index > pos) {
      parts.push({ type: "text", content: text.slice(pos, m.index) })
    }
    const raw = m[0]
    if (raw.startsWith("`")) {
      parts.push({ type: "code", content: raw.slice(1, -1) })
    } else {
      // **bold**
      parts.push({ type: "bold", content: raw.slice(2, -2) })
    }
    pos = m.index + raw.length
  }
  if (pos < text.length) {
    parts.push({ type: "text", content: text.slice(pos) })
  }

  return parts.map((part, i) => {
    if (part.type === "code") {
      return (
        <code
          key={i}
          className="rounded bg-surface-2 px-[0.35em] py-[0.1em] font-mono text-[0.85em] text-accent"
        >
          {part.content}
        </code>
      )
    }
    if (part.type === "bold") {
      return (
        <strong key={i} className="font-semibold text-ink">
          {part.content}
        </strong>
      )
    }
    return <span key={i}>{part.content}</span>
  })
}
