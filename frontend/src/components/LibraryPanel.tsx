import { useCallback, useRef, useState } from 'react'
import { UploadCloud, FileText, Image as ImageIcon, AudioLines, Trash2, Loader2, X } from 'lucide-react'
import type { LibraryFile, Modality } from '../types'

const ACCEPTED = '.pdf,.docx,.doc,.png,.jpg,.jpeg,.webp,.mp3,.wav,.m4a'

function ModalityIcon({ modality }: { modality: Modality }) {
  const cls = 'h-4 w-4 text-slate-400'
  if (modality === 'image') return <ImageIcon className={cls} />
  if (modality === 'audio') return <AudioLines className={cls} />
  return <FileText className={cls} />
}

/**
 * Per-chat Library drawer. Ingest/delete are delegated to the parent (App)
 * which owns the session id — so a brand-new chat gets a session created on
 * first upload. This library shows ONLY the current chat's files.
 */
export default function LibraryPanel({
  open, onClose, files, filesLoading, onIngest, onDeleteFile, onError,
}: {
  open: boolean
  onClose: () => void
  files: LibraryFile[]
  filesLoading: boolean
  onIngest: (files: File[]) => Promise<void>
  onDeleteFile: (name: string) => Promise<void>
  onError: (msg: string) => void
}) {
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const upload = useCallback(async (list: File[]) => {
    if (list.length === 0) return
    setUploading(true)
    try { await onIngest(list) } catch (err) { onError((err as Error).message) } finally { setUploading(false) }
  }, [onIngest, onError])

  async function remove(name: string) {
    setDeleting(name)
    try { await onDeleteFile(name) } catch (err) { onError((err as Error).message) } finally { setDeleting(null) }
  }

  return (
    <>
      {open && <div className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />}
      <div className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col bg-white shadow-2xl transition-transform duration-300 dark:bg-slate-900 ${open ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-800">
          <div>
            <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">Library — this chat</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">Files added here are searchable only in this chat</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="scroll-thin flex-1 overflow-y-auto p-5">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); upload(Array.from(e.dataTransfer.files)) }}
            onClick={() => inputRef.current?.click()}
            className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
              dragOver ? 'border-accent-400 bg-accent-50 dark:bg-accent-500/10'
                       : 'border-slate-300 bg-slate-50 hover:border-accent-300 dark:border-slate-700 dark:bg-slate-800'
            }`}
          >
            {uploading ? (
              <>
                <Loader2 className="mb-3 h-8 w-8 animate-spin text-accent-500" />
                <p className="text-sm font-medium text-slate-600 dark:text-slate-300">Indexing your files…</p>
                <p className="mt-1 text-xs text-slate-400">This can take a moment for PDFs and audio.</p>
              </>
            ) : (
              <>
                <UploadCloud className="mb-3 h-8 w-8 text-accent-500" />
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Drop files here or click to browse</p>
                <p className="mt-1 text-xs text-slate-400">PDF, DOCX, PNG, JPG, WEBP, MP3, WAV, M4A</p>
              </>
            )}
            <input ref={inputRef} type="file" multiple accept={ACCEPTED} className="hidden"
              onChange={(e) => { upload(Array.from(e.target.files ?? [])); e.target.value = '' }} />
          </div>

          <div className="mt-6">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Indexed files</h3>
              {filesLoading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
            </div>
            {files.length === 0 && !filesLoading ? (
              <p className="rounded-lg border border-dashed border-slate-200 px-4 py-6 text-center text-sm text-slate-400 dark:border-slate-700">
                No files in this chat yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {files.map((f) => (
                  <li key={f.file} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-800">
                    <ModalityIcon modality={f.modality} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-100" title={f.file}>{f.file}</p>
                      <p className="text-[11px] text-slate-400"><span className="capitalize">{f.modality}</span> · {f.chunks} chunk(s)</p>
                    </div>
                    <button onClick={() => remove(f.file)} disabled={deleting === f.file}
                      className="rounded-lg p-2 text-slate-400 transition hover:bg-red-50 hover:text-red-500 disabled:opacity-50 dark:hover:bg-red-500/10" title="Remove">
                      {deleting === f.file ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
