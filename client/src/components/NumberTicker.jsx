import { animate, useInView, useReducedMotion } from "motion/react"
import { useEffect, useRef } from "react"

import { ease } from "@/lib/motion"

const twoPlaces = (v) => v.toFixed(2)

/**
 * Counts up to `value` once it scrolls into view. The final text is always
 * the exact value; reduced motion shows it immediately. Pass a `format`
 * defined at module level so it stays the same between renders.
 */
export function NumberTicker({ value, format = twoPlaces, delay = 0, duration = 0.7, className }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: "-40px" })
  const reduce = useReducedMotion()

  useEffect(() => {
    const node = ref.current
    if (!node) return
    if (reduce) {
      node.textContent = format(value)
      return
    }
    if (!inView) return
    const controls = animate(0, value, {
      duration,
      delay,
      ease,
      onUpdate: (latest) => {
        node.textContent = format(latest)
      },
    })
    return () => controls.stop()
  }, [inView, reduce, value, delay, duration, format])

  return (
    <span ref={ref} className={className} aria-label={format(value)}>
      {format(reduce ? value : 0)}
    </span>
  )
}
