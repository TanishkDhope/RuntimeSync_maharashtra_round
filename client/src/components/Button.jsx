import { forwardRef } from "react"

import { cn } from "@/lib/cn"

import { Spinner } from "./Spinner"

const VARIANTS = {
  primary:
    "bg-ink text-paper hover:bg-ink-2 disabled:bg-rule-strong disabled:text-muted dark:bg-ink dark:text-paper",
  accent: "bg-accent text-on-accent hover:brightness-110 disabled:bg-rule-strong disabled:text-muted",
  secondary:
    "border border-rule-strong bg-surface text-ink hover:border-ink-2/60 hover:bg-surface-2 disabled:text-muted",
  ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink disabled:text-muted",
  // --paper is the page ground, light where --active is dark and dark where it
  // is light, so this reads correctly in both themes without a new token.
  danger: "bg-active text-paper hover:brightness-110 disabled:bg-rule-strong disabled:text-muted",
}

const SIZES = {
  sm: "h-8 gap-1.5 px-3 text-small",
  md: "h-10 gap-2 px-4 text-[15px]",
  lg: "h-12 gap-2.5 px-5 text-body",
  icon: "size-9 justify-center",
}

/**
 * The one button. `loading` keeps the width stable and swaps the leading icon
 * for a spinner; `hint` shows a keyboard shortcut.
 */
export const Button = forwardRef(function Button(
  { variant = "primary", size = "md", loading = false, hint, icon, className, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex shrink-0 select-none items-center rounded-control font-medium",
        "transition-[background-color,border-color,color,filter,transform] duration-150",
        "active:translate-y-px disabled:cursor-not-allowed",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {loading ? <Spinner className="size-4" /> : icon}
      {children}
      {hint && !loading && (
        <kbd className="ml-1 rounded border border-current/25 px-1.5 py-px font-mono text-[12px] opacity-70">
          {hint}
        </kbd>
      )}
    </button>
  )
})
