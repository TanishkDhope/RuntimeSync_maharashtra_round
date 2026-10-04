import { motion } from "motion/react"
import { useMemo, useState } from "react"

import { cn } from "@/lib/cn"
import { topicLabel } from "@/lib/format"
import { isNotServed, useBeliefGraph } from "@/lib/queries"

const W = 880
const H = 580
const CX = W / 2
const CY = H / 2
const TAU = Math.PI * 2
//: How far the topic hubs sit from the middle, and their beliefs from the hub.
const TOPIC_R = 150
const BELIEF_R = 96

const STATUS_COLOR = {
  active: "var(--active)",
  improving: "var(--improving)",
  resolved: "var(--exec)",
}

/**
 * The learner's beliefs and what sits next to them.
 *
 * Laid out by hand rather than with a force simulation: there are a dozen or
 * so nodes, the arrangement should be the same every time you open the page,
 * and a settling blob is harder to read than a fixed one. Topics sit on a
 * ring; their beliefs fan outwards from them.
 */
export function BeliefGraph({ learnerId }) {
  const graph = useBeliefGraph(learnerId)
  const [hovered, setHovered] = useState(null)

  const placed = useMemo(() => layout(graph.data?.nodes ?? []), [graph.data])

  if (graph.isPending) {
    return <Frame><div className="h-72 animate-pulse rounded-control bg-surface-2/70" /></Frame>
  }
  if (graph.error) {
    return (
      <Frame>
        <p className="py-8 text-body text-muted">
          {isNotServed(graph.error)
            ? "This backend doesn't serve the belief graph yet."
            : "Couldn't load the belief graph."}
        </p>
      </Frame>
    )
  }
  if (!graph.data?.nodes.length) {
    return (
      <Frame>
        <p className="py-8 text-body text-muted">
          Nothing diagnosed yet, so there is no neighbourhood to draw.
        </p>
      </Frame>
    )
  }

  const { edges, hidden_beliefs: hidden } = graph.data
  const focus = hovered && placed.get(hovered)
  const adjacent = new Set()
  if (hovered) {
    for (const edge of edges) {
      if (edge.source === hovered) adjacent.add(edge.target)
      if (edge.target === hovered) adjacent.add(edge.source)
    }
  }

  return (
    <Frame hidden={hidden}>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-auto w-full min-w-[640px]"
          role="img"
          aria-label="Belief graph: the misconceptions this learner has shown and the ones next to them"
        >
          <g>
            {edges.map((edge, index) => {
              const a = placed.get(edge.source)
              const b = placed.get(edge.target)
              if (!a || !b) return null
              const dim = hovered && edge.source !== hovered && edge.target !== hovered
              return (
                <line
                  key={`${edge.source}-${edge.target}-${index}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={edge.kind === "confusable" ? "var(--active)" : "var(--rule)"}
                  strokeWidth={edge.kind === "confusable" ? 1.6 : 1}
                  strokeDasharray={edge.kind === "co_occurs" ? "3 4" : undefined}
                  opacity={dim ? 0.12 : edge.kind === "in_topic" ? 0.5 : 0.75}
                />
              )
            })}
          </g>

          <g>
            {[...placed.entries()].map(([id, node]) => {
              const dim = hovered && id !== hovered && !adjacent.has(id)
              if (node.kind === "topic") {
                return (
                  <g key={id} opacity={dim ? 0.25 : 1}>
                    <circle cx={node.x} cy={node.y} r={30} fill="var(--surface-2)" stroke="var(--rule-strong)" />
                    <text
                      x={node.x}
                      y={node.y + 4}
                      textAnchor="middle"
                      className="fill-[var(--ink-2)] text-[12px] font-medium"
                    >
                      {topicLabel(node.label)}
                    </text>
                  </g>
                )
              }
              const color = STATUS_COLOR[node.status] ?? "var(--muted)"
              return (
                <motion.g
                  key={id}
                  opacity={dim ? 0.2 : 1}
                  onMouseEnter={() => setHovered(id)}
                  onMouseLeave={() => setHovered(null)}
                  className="cursor-pointer"
                >
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.held ? 9 + Math.min(node.times_seen, 4) : 5}
                    fill={node.held ? color : "var(--surface)"}
                    stroke={color}
                    strokeWidth={node.held ? 0 : 1.5}
                    strokeDasharray={node.held ? undefined : "2 2"}
                  />
                  <text
                    x={node.x}
                    y={node.y - (node.held ? 16 : 12)}
                    textAnchor="middle"
                    className={cn(
                      "text-[10px]",
                      node.held ? "fill-[var(--ink)] font-medium" : "fill-[var(--muted)]",
                    )}
                  >
                    {short(node.label)}
                  </text>
                </motion.g>
              )
            })}
          </g>
        </svg>
      </div>

      {focus?.kind === "belief" && (
        <p className="mt-2 min-h-[2.5rem] rounded-control bg-surface-2/60 px-3 py-2 text-small text-ink-2">
          <code className="font-mono text-[13px] text-muted">{focus.label}</code>
          {focus.description && <> — “{focus.description}”</>}
          {!focus.held && <span className="text-muted"> (never shown by this learner)</span>}
        </p>
      )}

      <GraphLegend />
    </Frame>
  )
}

function Frame({ children, hidden }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="overflow-hidden rounded-panel border border-rule bg-surface"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-6 py-4">
        <h2 className="font-serif text-h3 font-semibold text-ink">Belief graph</h2>
        <span className="text-small text-muted">
          {hidden ? `this learner's neighbourhood · ${hidden} more beliefs not shown` : "this learner's neighbourhood"}
        </span>
      </div>
      <div className="px-6 py-5">{children}</div>
    </motion.section>
  )
}

function GraphLegend() {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] text-muted">
      <Swatch color="var(--active)" label="still active" />
      <Swatch color="var(--improving)" label="improving" />
      <Swatch color="var(--exec)" label="resolved" />
      <span className="inline-flex items-center gap-1.5">
        <svg width="18" height="8" aria-hidden="true">
          <circle cx="5" cy="4" r="3.5" fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="2 2" />
        </svg>
        never shown — a neighbour
      </span>
      <span className="inline-flex items-center gap-1.5">
        <svg width="20" height="8" aria-hidden="true">
          <line x1="0" y1="4" x2="20" y2="4" stroke="var(--active)" strokeWidth="1.6" />
        </svg>
        easily confused with
      </span>
      <span className="inline-flex items-center gap-1.5">
        <svg width="20" height="8" aria-hidden="true">
          <line x1="0" y1="4" x2="20" y2="4" stroke="var(--rule)" strokeWidth="1" strokeDasharray="3 4" />
        </svg>
        tested by the same problems
      </span>
    </div>
  )
}

function Swatch({ color, label }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  )
}

/** Ids are SCREAMING_SNAKE and long; the graph only has room for a hint. */
function short(id) {
  return id.length <= 18 ? id : `${id.slice(0, 17)}…`
}

/**
 * Topic hubs on a ring; each hub's beliefs clustered around it.
 *
 * Deterministic: the same graph lands in the same place every time, so the
 * picture is comparable between visits. One topic is a special case - a ring
 * of one is a point, so its beliefs get the full circle instead.
 */
function layout(nodes) {
  const placed = new Map()
  const topics = nodes.filter((node) => node.kind === "topic")
  const beliefs = nodes.filter((node) => node.kind === "belief")
  if (!topics.length) return placed

  const byTopic = new Map(topics.map((topic) => [topic.topic, []]))
  const orphans = []
  for (const belief of beliefs) {
    const bucket = byTopic.get(belief.topic)
    if (bucket) bucket.push(belief)
    else orphans.push(belief)
  }

  const single = topics.length === 1

  topics.forEach((topic, index) => {
    const angle = single ? 0 : (index / topics.length) * TAU - Math.PI / 2
    const hub = single
      ? { x: CX, y: CY }
      : { x: CX + Math.cos(angle) * TOPIC_R, y: CY + Math.sin(angle) * TOPIC_R }
    placed.set(topic.id, { ...topic, ...hub })

    const kids = byTopic.get(topic.topic) ?? []
    if (!kids.length) return

    // Each topic's beliefs ring their own hub rather than a shared circle, so
    // a topic reads as a cluster and its in-topic edges stay short. The fan
    // opens away from the middle, where the other hubs are.
    const arc = single ? TAU : Math.min(TAU * 0.72, 0.5 * kids.length + 0.6)
    const step = kids.length === 1 ? 0 : arc / (kids.length - 1)

    kids.forEach((belief, j) => {
      const a = single ? (j / kids.length) * TAU : angle - arc / 2 + j * step
      // Alternating radii on a crowded fan: labels sit above their node, and
      // neighbours at one radius overlap each other's text.
      const r = kids.length > 3 && j % 2 ? BELIEF_R * 1.32 : BELIEF_R
      placed.set(belief.id, { ...belief, x: hub.x + Math.cos(a) * r, y: hub.y + Math.sin(a) * r })
    })
  })

  // Anything the server sent without a topic still has to land somewhere.
  orphans.forEach((belief, index) => {
    placed.set(belief.id, { ...belief, x: 70 + index * 76, y: H - 24 })
  })

  return placed
}
