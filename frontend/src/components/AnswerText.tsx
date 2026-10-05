import { Fragment } from 'react'

/** Renders an answer and turns [1], [2] markers into clickable chips. */
export default function AnswerText({
  text, onCitationClick, validIndexes,
}: {
  text: string
  onCitationClick: (index: number) => void
  validIndexes?: Set<number>
}) {
  const parts = text.split(/\[(\d+)\]/g)
  return (
    <p className="whitespace-pre-wrap leading-relaxed text-slate-800 dark:text-slate-100">
      {parts.map((part, i) => {
        const isMarker = i % 2 === 1
        if (!isMarker) return <Fragment key={i}>{part}</Fragment>
        const n = parseInt(part, 10)
        if (validIndexes && !validIndexes.has(n)) {
          return <Fragment key={i}>[{part}]</Fragment>
        }
        return (
          <sup key={i} className="mx-0.5">
            <button
              type="button"
              onClick={() => onCitationClick(n)}
              className="inline-flex h-4 min-w-4 items-center justify-center rounded bg-accent-100 px-1 text-[10px] font-semibold text-accent-700 transition hover:bg-accent-600 hover:text-white dark:bg-accent-500/25 dark:text-accent-200"
              title={`Jump to source [${n}]`}
            >
              {n}
            </button>
          </sup>
        )
      })}
    </p>
  )
}
