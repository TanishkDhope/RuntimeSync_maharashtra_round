/**
 * Motion tokens. Motion explains a change of state; it never decorates.
 * MotionConfig reducedMotion="user" (app/Providers.jsx) turns transforms and
 * layout animation off for people who ask for less motion; opacity remains.
 */

export const ease = [0.22, 1, 0.36, 1]

export const duration = {
  fast: 0.15,
  base: 0.22,
  slow: 0.42,
  signature: 0.9,
}

export const spring = { type: "spring", stiffness: 380, damping: 34, mass: 0.9 }

export const base = { duration: duration.base, ease }

/** A new section arriving in the case thread. */
export const rise = {
  hidden: { opacity: 0, y: 8 },
  shown: { opacity: 1, y: 0, transition: { duration: duration.slow, ease } },
}

/** Children appearing one after another (score rows, checklist items). */
export const stagger = (gap = 0.06, delay = 0) => ({
  hidden: {},
  shown: { transition: { staggerChildren: gap, delayChildren: delay } },
})

export const fade = {
  hidden: { opacity: 0 },
  shown: { opacity: 1, transition: { duration: duration.base, ease } },
}
