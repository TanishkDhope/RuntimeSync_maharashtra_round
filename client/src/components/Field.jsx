import { forwardRef } from "react"

import { cn } from "@/lib/cn"

export function Label({ htmlFor, children, hint, className }) {
  return (
    <label htmlFor={htmlFor} className={cn("flex items-baseline justify-between gap-3", className)}>
      <span className="text-[15px] font-medium text-ink">{children}</span>
      {hint && <span className="text-small text-muted">{hint}</span>}
    </label>
  )
}

const control =
  "w-full rounded-control border border-rule-strong bg-surface px-3.5 text-body text-ink placeholder:text-muted/80 " +
  "transition-[border-color,box-shadow] duration-150 hover:border-ink-2/50 " +
  "focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15 disabled:bg-surface-2 disabled:text-muted"

export const TextInput = forwardRef(function TextInput({ className, ...props }, ref) {
  return <input ref={ref} className={cn(control, "h-12", className)} {...props} />
})

/** The program's output, typed the way a console shows it. */
export const OutputPad = forwardRef(function OutputPad({ className, value, rows, ...props }, ref) {
  const lineCount = Math.max(3, Math.min(10, (value ?? "").split("\n").length + 1))
  return (
    <div
      className={cn(
        "overflow-hidden rounded-panel border border-rule-strong bg-surface transition-[border-color,box-shadow] duration-150",
        "focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15",
        className,
      )}
    >
      <div className="flex h-9 items-center justify-between border-b border-rule bg-surface-2/60 px-4 font-mono text-[13px] text-muted">
        <span>stdout</span>
        <span>one printed line per line</span>
      </div>
      <textarea
        ref={ref}
        value={value}
        rows={rows ?? lineCount}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        className="block w-full resize-none bg-transparent px-4 py-3 font-mono text-code text-ink placeholder:text-muted/70 focus:outline-none disabled:text-muted"
        {...props}
      />
    </div>
  )
})
