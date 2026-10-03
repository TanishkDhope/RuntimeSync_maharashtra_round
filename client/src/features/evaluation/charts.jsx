import { motion, useInView } from "motion/react"
import { useRef } from "react"

import { cn } from "@/lib/cn"
import { ease } from "@/lib/motion"

const TONE = {
  accent: "bg-accent",
  muted: "bg-muted/45",
  exec: "bg-exec",
}

/**
 * Horizontal grouped bars on a fixed 0–100% axis, so lengths compare honestly
 * across rows. Bars grow when the chart scrolls into view.
 * rows: [{label, sub?, bars: [{key, label, tone, value}]}]
 */
export function BarChart({ rows, legend }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: "-60px" })

  return (
    <div ref={ref} className="space-y-5">
      {legend && legend.length > 1 && (
        <div className="flex flex-wrap gap-4 text-small text-muted">
          {legend.map((item) => (
            <span key={item.key} className="flex items-center gap-2">
              <span className={cn("h-2.5 w-5 rounded-full", TONE[item.tone])} />
              {item.label}
            </span>
          ))}
        </div>
      )}
      <div className="space-y-5">
        {rows.map((row, r) => (
          <div key={row.label} className="grid gap-x-6 gap-y-2 md:grid-cols-[240px_minmax(0,1fr)]">
            <div>
              <p className="text-[15px] font-medium text-ink">{row.label}</p>
              {row.sub && <p className="text-small text-muted">{row.sub}</p>}
            </div>
            <div className="space-y-1.5">
              {row.bars.map((bar, b) => (
                <div key={bar.key} className="flex items-center gap-3">
                  <div className="relative h-3.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                    <motion.div
                      className={cn("absolute inset-y-0 left-0 origin-left rounded-full", TONE[bar.tone])}
                      style={{ width: `${Math.max(0, Math.min(1, bar.value)) * 100}%` }}
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: inView ? 1 : 0 }}
                      transition={{ duration: 0.8, delay: r * 0.08 + b * 0.05, ease }}
                    />
                    {[0.25, 0.5, 0.75].map((tick) => (
                      <span key={tick} className="absolute inset-y-0 w-px bg-paper/70" style={{ left: `${tick * 100}%` }} />
                    ))}
                  </div>
                  <span
                    className={cn(
                      "w-[4.5rem] shrink-0 text-right font-mono text-[15px] tabular",
                      bar.tone === "accent" ? "font-semibold text-ink" : "text-ink-2",
                    )}
                  >
                    {(bar.value * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="hidden grid-cols-[240px_minmax(0,1fr)] gap-x-6 md:grid">
        <span />
        <div className="mr-[5.25rem] flex justify-between font-mono text-[12px] text-muted">
          <span>0%</span>
          <span>25%</span>
          <span>50%</span>
          <span>75%</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  )
}

/** Row-normalised confusion heatmap (true belief by first choice). */
export function Heatmap({ labels, matrix }) {
  const rowTotals = matrix.map((row) => row.reduce((a, b) => a + b, 0) || 1)
  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-[2px] font-mono text-[11.5px]">
        <thead>
          <tr>
            <th />
            {labels.map((label) => (
              <th key={label} className="h-28 w-7 align-bottom font-normal text-muted">
                <span className="inline-block origin-bottom-left -rotate-60 translate-x-3 whitespace-nowrap">{label}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={labels[i]}>
              <th className="whitespace-nowrap pr-2 text-right font-normal text-muted">{labels[i]}</th>
              {row.map((value, j) => {
                const share = value / rowTotals[i]
                return (
                  <td
                    key={j}
                    title={`${labels[i]} → ${labels[j]}: ${value}`}
                    className={cn("size-7 rounded-[3px]", i === j && "ring-1 ring-ink/20")}
                    style={{ background: `color-mix(in oklab, var(--accent) ${Math.round(share * 100)}%, var(--surface-2))` }}
                  />
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
