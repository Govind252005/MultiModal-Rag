import { useRef, useState } from 'react'
import { Send, Mic, Square, Image as ImageIcon, AudioLines, Loader2 } from 'lucide-react'
import type { LibraryFile, Scope } from '../types'
import ScopePanel from './ScopePanel'

/**
 * Bottom composer: text input + Send, a search-scope selector, top-k, a mic
 * (record -> transcribe -> auto submit), and image/audio query buttons.
 * Recording is local; transcription is delegated to the parent via
 * `transcribeBlob` so session handling stays in App.
 */
export default function Composer({
  onSubmitText, onImageQuery, onAudioQuery, transcribeBlob, onError, busy,
  scope, setScope, files, topK, setTopK,
}: {
  onSubmitText: (text: string) => void
  onImageQuery: (file: File) => void
  onAudioQuery: (file: File) => void
  transcribeBlob: (blob: Blob) => Promise<string>
  onError: (msg: string) => void
  busy: boolean
  scope: Scope
  setScope: (s: Scope) => void
  files: LibraryFile[]
  topK: number
  setTopK: (n: number) => void
}) {
  const [input, setInput] = useState('')
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const audioInputRef = useRef<HTMLInputElement>(null)

  function submit() {
    const q = input.trim()
    if (!q || busy) return
    onSubmitText(q)
    setInput('')
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const recorder = new MediaRecorder(stream)
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      recorder.onstop = handleRecordingStop
      recorder.start()
      recorderRef.current = recorder
      setRecording(true)
    } catch {
      onError('Microphone permission denied or unavailable.')
    }
  }

  function stopRecording() {
    recorderRef.current?.stop()
    setRecording(false)
  }

  async function handleRecordingStop() {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
    if (blob.size === 0) return
    setTranscribing(true)
    try {
      const clean = (await transcribeBlob(blob)).trim()
      if (!clean) { onError('Could not transcribe any speech.'); return }
      setInput(clean)
      onSubmitText(clean)
      setInput('')
    } catch (err) {
      onError((err as Error).message)
    } finally {
      setTranscribing(false)
    }
  }

  return (
    <div className="border-t border-slate-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-900 sm:px-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <ScopePanel files={files} scope={scope} setScope={setScope} />

        <label className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-3 pr-2 text-xs font-medium text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
          top-k
          <input
            type="number" min={1} max={20} value={topK}
            onChange={(e) => setTopK(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
            className="w-11 rounded border-none bg-transparent text-center outline-none"
            title="How many chunks to retrieve"
          />
        </label>

        <div className="ml-auto flex items-center gap-1.5">
          <button onClick={() => imageInputRef.current?.click()} disabled={busy}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:border-accent-300 hover:text-accent-600 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            title="Query with an image">
            <ImageIcon className="h-4 w-4" /><span className="hidden sm:inline">Image</span>
          </button>
          <input ref={imageInputRef} type="file" accept="image/*" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onImageQuery(f); e.target.value = '' }} />

          <button onClick={() => audioInputRef.current?.click()} disabled={busy}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:border-accent-300 hover:text-accent-600 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            title="Query with an audio clip">
            <AudioLines className="h-4 w-4" /><span className="hidden sm:inline">Audio</span>
          </button>
          <input ref={audioInputRef} type="file" accept="audio/*" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onAudioQuery(f); e.target.value = '' }} />
        </div>
      </div>

      {(recording || transcribing) && (
        <div className="mb-2 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:bg-red-500/10 dark:text-red-400">
          {recording ? (
            <><span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-red-500" /> Recording… tap stop when done.</>
          ) : (
            <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Transcribing…</>
          )}
        </div>
      )}

      <div className="flex items-end gap-2">
        <button
          onClick={recording ? stopRecording : startRecording}
          disabled={busy || transcribing}
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border transition disabled:opacity-50 ${
            recording ? 'border-red-300 bg-red-500 text-white hover:bg-red-600'
                      : 'border-slate-200 bg-white text-slate-500 hover:border-accent-300 hover:text-accent-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400'
          }`}
          title={recording ? 'Stop recording' : 'Voice query'}
        >
          {recording ? <Square className="h-4 w-4" /> : <Mic className="h-5 w-5" />}
        </button>

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
          rows={1}
          placeholder="Ask about your documents, images or audio…"
          className="scroll-thin max-h-40 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-accent-400 focus:bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:bg-slate-800"
        />

        <button
          onClick={submit}
          disabled={busy || !input.trim()}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-600 text-white transition hover:bg-accent-700 disabled:opacity-40"
          title="Send"
        >
          {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
        </button>
      </div>
    </div>
  )
}
