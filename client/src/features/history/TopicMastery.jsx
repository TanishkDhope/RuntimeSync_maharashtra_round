import { motion } from "motion/react"
import { useMemo } from "react"

import { cn } from "@/lib/cn"
import { topicLabel } from "@/lib/format"
import { rise, stagger } from "@/lib/motion"

/**
 * Which topics this learner is solid on and which they are not.
 *
 * The server has computed this on every history request since the endpoint
 * existed; nothing rendered it. Accuracy alone would be misleading, so the
 * count of beliefs still active in a topic sits next to it: 80% with two live
 * misconceptions is a different situation from 80% with none.
 */
export function TopicMastery({ topics }) {
  const sorted = useMemo(
    () =>
      [...(topics ?? [])].sort(
        (a, b) => a.accuracy_percent - b.accuracy_percent || b.total_attempts - a.total_attempts,
      ),
    [topics],
  )

  if (!sorted.length) return null

  // Weakest first, so the thing worth doing next is at the top.
  const weakest = sorted[0]

  return (
    <motion.section
      variants={rise}
      initial="hidden"
      animate="shown"
      className="overflow-hidden rounded-panel border border-rule bg-surface"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-6 py-4">
        <h2 className="font-serif text-h3 font-semibold text-ink">Topics</h2>
        <span className="text-small text-muted">weakest first</span>
      </div>

      <motion.ul variants={stagger(0.05)} initial="hidden" animate="shown" className="divide-y divide-rule">
        {sorted.map((topic) => (
          <motion.li key={topic.topic} variants={rise} className="flex flex-wrap items-center gap-4 px-6 py-4">
            <div className="min-w-[140px] flex-1">
              <p className="font-medium text-ink">{topicLabel(topic.topic)}</p>
              <p className="mt-0.5 text-[13px] text-muted">
                {topic.correct_attempts} of {topic.total_attempts} correct
                {topic.active_misconceptions_count > 0 && (
                  <>
                    {" · "}
                    <span className="text-active">
                      {topic.active_misconceptions_count} belief
                      {topic.active_misconceptions_count === 1 ? "" : "s"} still active
                    </span>
                  </>
                )}
              </p>
            </div>

            <div className="flex min-w-[180px] flex-1 items-center gap-3">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-rule">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.max(2, topic.accuracy_percent)}%` }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                  className={cn("h-full rounded-full", bandClass(topic))}
                />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-small tabular text-ink-2">
                {topic.accuracy_percent.toFixed(0)}%
              </span>
            </div>
          </motion.li>
        ))}
      </motion.ul>

      {weakest.total_attempts > 0 && (
        <p className="border-t border-rule px-6 py-3 text-small text-muted">
          Weakest right now: <span className="font-medium text-ink">{topicLabel(weakest.topic)}</span> at{" "}
          {weakest.accuracy_percent.toFixed(0)}%.
        </p>
      )}
    </motion.section>
  )
}

/**
 * Colour follows the belief statuses, not the percentage alone: a topic with
 * a live misconception is not "good" however well the last few answers went.
 */
function bandClass(topic) {
  if (topic.active_misconceptions_count > 0) return "bg-active"
  if (topic.accuracy_percent >= 80) return "bg-exec"
  if (topic.accuracy_percent >= 50) return "bg-improving"
  return "bg-active"
}
