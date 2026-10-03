import { cn } from "@/lib/cn"

import { ProvenanceTag } from "./ProvenanceTag"

/** write_code results: each call, what was expected, what came back. */
export function TestResults({ results }) {
  const passed = results.filter((row) => row.passed).length
  return (
    <div className="space-y-2">
      <div className="flex h-7 items-center justify-between gap-2">
        <span className="text-small font-medium text-muted">
          Tests: {passed} of {results.length} passed
        </span>
        <ProvenanceTag kind="exec" />
      </div>
      <div className="overflow-x-auto rounded-panel border border-rule">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-rule bg-surface-2/60 text-small text-muted">
              <th className="px-4 py-2 font-medium">Call</th>
              <th className="px-4 py-2 font-medium">Expected</th>
              <th className="px-4 py-2 font-medium">Got</th>
              <th className="w-14 px-4 py-2 text-right font-medium">
                <span className="sr-only">Result</span>
              </th>
            </tr>
          </thead>
          <tbody className="font-mono text-[15px]">
            {results.map((row) => (
              <tr key={row.call} className="border-b border-rule last:border-0">
                <td className="px-4 py-2.5">{row.call}</td>
                <td className="px-4 py-2.5 text-ink-2">{row.expected}</td>
                <td className={cn("px-4 py-2.5", !row.passed && "text-active")}>
                  {row.error ? <span className="font-sans text-small">{row.error}</span> : row.got}
                </td>
                <td className="px-4 py-2.5 text-right font-sans text-small font-semibold">
                  {row.passed ? (
                    <span className="text-exec">✓ pass</span>
                  ) : (
                    <span className="text-active">✗ fail</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
