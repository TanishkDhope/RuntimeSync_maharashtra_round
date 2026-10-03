import { lazy, Suspense } from "react"

import { cn } from "@/lib/cn"

// CodeMirror is only needed for write_code answers, so it loads on demand.
const CodeMirrorEditor = lazy(() => import("./CodeMirrorEditor"))

/** Python editor for write_code answers, styled like the read-only panel. */
export function CodeEditor({ className, label = "your_solution.py", ...props }) {
  return (
    <div
      className={cn(
        "code-surface overflow-hidden rounded-panel border border-code-rule bg-code-bg focus-within:border-accent",
        className,
      )}
    >
      <div className="flex h-9 items-center justify-between border-b border-code-rule px-4 font-mono text-[13px] text-code-muted">
        <span>{label}</span>
        <span>Python</span>
      </div>
      <Suspense fallback={<div className="h-[240px] animate-pulse bg-white/[0.02]" aria-label="Loading editor" />}>
        <CodeMirrorEditor {...props} />
      </Suspense>
    </div>
  )
}
