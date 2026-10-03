/** DEV-ONLY banner shown whenever the sample backend is active. */
export default function SampleStrip() {
  return (
    <div role="status" className="hatch bg-ink text-paper">
      <div className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-x-3 gap-y-1 px-6 py-1.5 text-small lg:px-10">
        <span className="font-semibold uppercase tracking-[0.08em]">SAMPLE DATA · not from the model</span>
        <span className="opacity-75">
          Dev preview of steps the backend doesn't serve yet. Scores and evaluation numbers are invented.
        </span>
      </div>
    </div>
  )
}
