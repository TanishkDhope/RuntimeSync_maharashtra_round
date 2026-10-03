/**
 * Read-only program display with line numbers. Deliberately plain and large:
 * this has to be legible from the back of a room.
 */
export function CodeViewer({ code, highlightLine }) {
  const lines = code.replace(/\r\n/g, "\n").split("\n")

  return (
    <div className="overflow-x-auto rounded-md border bg-zinc-950 py-3 font-mono text-[15px] leading-relaxed">
      <table className="w-full border-collapse">
        <tbody>
          {lines.map((line, index) => {
            const number = index + 1
            const isHighlighted = number === highlightLine
            return (
              <tr key={number} className={isHighlighted ? "bg-amber-500/15" : undefined}>
                <td className="w-10 select-none border-r border-zinc-800 px-3 text-right align-top text-zinc-600">
                  {number}
                </td>
                <td className="whitespace-pre px-4 align-top text-zinc-100">
                  {line || " "}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** Program output, shown the way the student typed it or the way it really is. */
export function OutputBlock({ text, tone = "neutral" }) {
  const tones = {
    neutral: "border-border bg-muted/50 text-foreground",
    correct: "border-emerald-600/40 bg-emerald-600/10 text-emerald-200",
    wrong: "border-red-600/40 bg-red-600/10 text-red-200",
  }

  return (
    <pre
      className={`overflow-x-auto whitespace-pre rounded-md border px-3 py-2 font-mono text-[15px] leading-relaxed ${tones[tone]}`}
    >
      {text === "" || text == null ? (
        <span className="italic opacity-60">(nothing)</span>
      ) : (
        text
      )}
    </pre>
  )
}
