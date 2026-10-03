import { motion } from "motion/react"
import { lazy, Suspense } from "react"
import { Outlet, useLocation } from "react-router"

import { ease } from "@/lib/motion"
import { useHealth } from "@/lib/queries"

import { Header } from "./Header"

// Dev-only banner; the condition is a build-time constant, so production
// builds drop it (and the mocks it lives with).
const SampleStrip =
  import.meta.env.DEV && import.meta.env.VITE_SAMPLE_STEPS === "1"
    ? lazy(() => import("../mocks/SampleStrip"))
    : null

export function Shell() {
  const location = useLocation()
  const health = useHealth()
  const stub = health.data && !health.data.diagnoser_is_real_model

  return (
    <div className="flex min-h-dvh flex-col">
      {SampleStrip && (
        <Suspense fallback={null}>
          <SampleStrip />
        </Suspense>
      )}
      <Header health={health} />
      {stub && <StubStrip />}
      <motion.main
        key={location.pathname}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease }}
        className="flex-1"
      >
        <Outlet />
      </motion.main>
    </div>
  )
}

/** Impossible to miss: nobody should demo the stub by accident. */
function StubStrip() {
  return (
    <div role="status" className="hatch border-b border-hazard/60 bg-hazard/30 text-hazard-ink dark:bg-hazard/15 dark:text-hazard">
      <div className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-x-3 gap-y-1 px-6 py-2 text-small lg:px-10">
        <span className="font-semibold uppercase tracking-[0.08em]">Stub diagnoser active</span>
        <span>
          Rankings come from matching predicted outputs, not from the trained model. Set{" "}
          <code className="font-mono">DIAGNOSER=model</code> on the server to use it.
        </span>
      </div>
    </div>
  )
}
