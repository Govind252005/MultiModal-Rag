import { useState } from 'react'
import { SlidersHorizontal, ChevronDown, FileText, Image as ImageIcon, AudioLines, Check } from 'lucide-react'
import type { LibraryFile, ModalityFilter, Modality, Scope } from '../types'

const MODALITIES: { value: ModalityFilter; label: string }[] = [
  { value: 'all', label: 'All types' },
  { value: 'document', label: 'Documents' },
  { value: 'image', label: 'Images' },
  { value: 'audio', label: 'Audio' },
]

function Icon({ m }: { m: Modality }) {
  const c = 'h-3.5 w-3.5 text-slate-400'
  if (m === 'image') return <ImageIcon className={c} />
  if (m === 'audio') return <AudioLines className={c} />
  return <FileText className={c} />
}

/**
 * Search-scope selector: pick a modality AND/OR specific files to search.
 * `scope.files` empty = search all files in the chat. This is what lets you
 * say "search ONLY this image" and get nothing from other sources.
 */
export default function ScopePanel({
  files, scope, setScope,
}: {
  files: LibraryFile[]
  scope: Scope
  setScope: (s: Scope) => void
}) {
  const [open, setOpen] = useState(false)

  const toggleFile = (name: string) => {
    const set = new Set(scope.files)
    set.has(name) ? set.delete(name) : set.add(name)
    setScope({ ...scope, files: Array.from(set) })
  }

  const label =
    scope.files.length > 0
      ? `${scope.files.length} file(s)`
      : MODALITIES.find((m) => m.value === scope.modality)?.label || 'All'

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-2.5 pr-2 text-xs font-medium text-slate-600 transition hover:border-accent-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
        title="Choose which sources to search"
      >
        <SlidersHorizontal className="h-3.5 w-3.5" />
        <span>Scope: {label}</span>
        <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-30 mb-2 w-72 rounded-xl border border-slate-200 bg-white p-3 shadow-xl dark:border-slate-700 dark:bg-slate-800">
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Type</p>
          <div className="mb-3 grid grid-cols-2 gap-1.5">
            {MODALITIES.map((m) => (
              <button
                key={m.value}
                onClick={() => setScope({ ...scope, modality: m.value })}
                className={`rounded-lg px-2 py-1.5 text-xs font-medium transition ${
                  scope.modality === m.value
                    ? 'bg-accent-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          <div className="mb-1.5 flex items-center justify-between">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Files</p>
            {scope.files.length > 0 && (
              <button onClick={() => setScope({ ...scope, files: [] })} className="text-[11px] font-medium text-accent-600 hover:underline">
                Clear (all)
              </button>
            )}
          </div>
          {files.length === 0 ? (
            <p className="py-2 text-xs text-slate-400">No files in this chat yet.</p>
          ) : (
            <ul className="scroll-thin max-h-40 space-y-1 overflow-y-auto">
              {files.map((f) => {
                const checked = scope.files.includes(f.file)
                return (
                  <li key={f.file}>
                    <button
                      onClick={() => toggleFile(f.file)}
                      className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                    >
                      <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${checked ? 'border-accent-600 bg-accent-600 text-white' : 'border-slate-300 dark:border-slate-600'}`}>
                        {checked && <Check className="h-3 w-3" />}
                      </span>
                      <Icon m={f.modality} />
                      <span className="min-w-0 flex-1 truncate" title={f.file}>{f.file}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
          <p className="mt-2 text-[10px] leading-snug text-slate-400">
            Tick files to restrict the search to them only. Nothing ticked = all files of the chosen type.
          </p>
        </div>
      )}
    </div>
  )
}
