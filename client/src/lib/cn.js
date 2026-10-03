import { clsx } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

// Teach tailwind-merge our custom size and radius names; otherwise it reads
// `text-body` as a colour and drops it when merged with `text-ink`.
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["eyebrow", "small", "body", "code", "h3", "belief", "h2", "h1", "display"],
      radius: ["control", "panel"],
    },
  },
})

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
