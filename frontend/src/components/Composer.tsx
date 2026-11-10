import React, { useRef, useState, useEffect } from 'react'
import {
  Send,
  Square,
  Paperclip,
  Image as ImageIcon,
  Mic,
  AudioLines,
  FileText,
  X,
  Loader2,
  StopCircle,
  ShieldCheck,
  Layers,
} from 'lucide-react'
import type { LibraryFile, Scope, ActiveProviderResponse } from '../types'
import ScopePanel from './ScopePanel'

export interface StagedAttachment {
  id: string
  file: File
  type: 'image' | 'audio' | 'document'
  previewUrl?: string
  transcript?: string
  transcribing?: boolean
}

export interface ComposerProps {
  onSubmitText: (text: string) => void
  onImageQuery: (file: File, query?: string) => void
  onAudioQuery: (file: File, query?: string) => void
  onIngestAndQuery?: (files: File[], query: string) => Promise<void>
  onStopGeneration?: () => void
  transcribeBlob: (blob: Blob) => Promise<string>
  onError: (msg: string) => void
  busy: boolean
  scope: Scope
  setScope: (s: Scope) => void
  files: LibraryFile[]
  topK: number
  setTopK: (n: number) => void
  activeProvider?: ActiveProviderResponse | null
}

const SUPPORTED_DOCS = '.pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.txt,.csv,.md,.json,.log'
const SUPPORTED_IMAGES = '.png,.jpg,.jpeg,.webp,.gif,.bmp'
const SUPPORTED_AUDIO = '.mp3,.wav,.m4a,.flac,.ogg,.webm'

export default function Composer({
  onSubmitText,
  onImageQuery,
  onAudioQuery,
  onIngestAndQuery,
  onStopGeneration,
  transcribeBlob,
  onError,
  busy,
  scope,
  setScope,
  files,
  topK,
  setTopK,
  activeProvider,
}: ComposerProps) {
  const [input, setInput] = useState('')
  const [stagedFiles, setStagedFiles] = useState<StagedAttachment[]>([])
  const [recording, setRecording] = useState(false)
  const [recordingDuration, setRecordingDuration] = useState(0)
  const [dragOver, setDragOver] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const audioInputRef = useRef<HTMLInputElement>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<any>(null)
  const speechRecRef = useRef<any>(null)

  // Auto-resize textarea as user types
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`
    }
  }, [input])

  // Recording timer
  useEffect(() => {
    if (recording) {
      setRecordingDuration(0)
      timerRef.current = setInterval(() => {
        setRecordingDuration((p) => p + 1)
      }, 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [recording])

  // Helper to format bytes
  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Stage an incoming file
  function stageFile(file: File) {
    const ext = `.${file.name.split('.').pop()?.toLowerCase()}`
    let type: 'image' | 'audio' | 'document' = 'document'
    let previewUrl: string | undefined = undefined

    if (SUPPORTED_IMAGES.split(',').includes(ext) || file.type.startsWith('image/')) {
      type = 'image'
      previewUrl = URL.createObjectURL(file)
    } else if (SUPPORTED_AUDIO.split(',').includes(ext) || file.type.startsWith('audio/')) {
      type = 'audio'
      previewUrl = URL.createObjectURL(file)
    }

    const newAttachment: StagedAttachment = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file,
      type,
      previewUrl,
    }

    setStagedFiles((prev) => [...prev, newAttachment])

    // If it's an audio file, trigger background transcription review without auto-submitting
    if (type === 'audio') {
      newAttachment.transcribing = true
      transcribeBlob(file)
        .then((text) => {
          const trimmed = text.trim()
          setStagedFiles((current) =>
            current.map((att) =>
              att.id === newAttachment.id
                ? { ...att, transcript: trimmed, transcribing: false }
                : att
            )
          )
          // Populate the prompt query textarea so the user can immediately review, edit, and add instructions!
          if (trimmed) {
            setInput((prev) => {
              const currentInput = prev.trim()
              if (!currentInput) return trimmed
              if (!currentInput.includes(trimmed)) return `${currentInput}\n${trimmed}`
              return prev
            })
          }
        })
        .catch(() => {
          setStagedFiles((current) =>
            current.map((att) =>
              att.id === newAttachment.id ? { ...att, transcribing: false } : att
            )
          )
        })
    }
  }

  function removeStaged(id: string) {
    setStagedFiles((prev) => {
      const target = prev.find((item) => item.id === id)
      if (target?.previewUrl) {
        URL.revokeObjectURL(target.previewUrl)
      }
      return prev.filter((item) => item.id !== id)
    })
  }

  // Voice recording with live speech-to-text review
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const recorder = new MediaRecorder(stream)
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = handleRecordingStop
      recorder.start()
      recorderRef.current = recorder
      setRecording(true)

      // Start live speech-to-text if Web Speech API is supported
      if (typeof window !== 'undefined') {
        const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
        if (SpeechRec) {
          try {
            const rec = new SpeechRec()
            rec.continuous = true
            rec.interimResults = true
            rec.onresult = (evt: any) => {
              let liveText = ''
              for (let i = 0; i < evt.results.length; ++i) {
                liveText += evt.results[i][0].transcript
              }
              if (liveText.trim()) {
                setInput(liveText.trim())
              }
            }
            rec.onerror = () => {
              // Graceful fallback to backend Whisper on stop
            }
            rec.start()
            speechRecRef.current = rec
          } catch {
            // SpeechRec init failed, fallback to backend transcribe on stop
          }
        }
      }
    } catch {
      onError('Microphone permission denied or device unavailable.')
    }
  }

  function stopRecording() {
    if (speechRecRef.current) {
      try {
        speechRecRef.current.stop()
      } catch {}
      speechRecRef.current = null
    }
    recorderRef.current?.stop()
    setRecording(false)
  }

  async function handleRecordingStop() {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
    if (blob.size === 0) return

    const recordedFile = new File([blob], `voice-recording-${new Date().toISOString().slice(11, 19).replace(/:/g, '')}.webm`, {
      type: 'audio/webm',
    })

    // Stage the audio for review — strictly DO NOT auto-submit!
    stageFile(recordedFile)
  }

  // Main Submit Action
  async function handleSubmit(e?: React.FormEvent) {
    if (e) e.preventDefault()
    if (busy) {
      if (onStopGeneration) onStopGeneration()
      return
    }

    const queryText = input.trim()

    // 1. Image staged: execute image query with custom prompt
    const stagedImage = stagedFiles.find((f) => f.type === 'image')
    if (stagedImage) {
      onImageQuery(stagedImage.file, queryText)
      setStagedFiles((prev) => prev.filter((f) => f.id !== stagedImage.id))
      setInput('')
      return
    }

    // 2. Audio staged: execute audio query with custom prompt
    const stagedAudio = stagedFiles.find((f) => f.type === 'audio')
    if (stagedAudio) {
      onAudioQuery(stagedAudio.file, queryText)
      setStagedFiles((prev) => prev.filter((f) => f.id !== stagedAudio.id))
      setInput('')
      return
    }

    // 3. Document(s) staged: ingest and answer
    const stagedDocs = stagedFiles.filter((f) => f.type === 'document')
    if (stagedDocs.length > 0 && onIngestAndQuery) {
      const docFiles = stagedDocs.map((d) => d.file)
      setStagedFiles((prev) => prev.filter((f) => f.type !== 'document'))
      setInput('')
      await onIngestAndQuery(docFiles, queryText || 'Summarize the attached document(s) and highlight main points.')
      return
    }

    // 4. Text query only
    if (!queryText) return
    onSubmitText(queryText)
    setInput('')
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragOver(false)
        Array.from(e.dataTransfer.files).forEach(stageFile)
      }}
      className={`border-t border-surface-200 dark:border-surface-800 bg-white dark:bg-surface-900 p-3 sm:p-4 transition-colors ${
        dragOver ? 'bg-brand-50/60 dark:bg-brand-950/20' : ''
      }`}
    >
      <div className="max-w-4xl mx-auto space-y-3">
        {/* Scope and Top-K Header Strip */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2">
            <ScopePanel files={files} scope={scope} setScope={setScope} />
            {scope.collection_name && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-brand-200 bg-brand-50 text-brand-700 text-xs font-medium dark:border-brand-900/60 dark:bg-brand-950/40 dark:text-brand-300">
                <Layers className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
                Collection: {scope.collection_name}
                <button
                  type="button"
                  onClick={() => setScope({ ...scope, collection_id: undefined, collection_name: undefined })}
                  className="ml-0.5 rounded p-0.5 hover:bg-brand-100 dark:hover:bg-brand-900/60"
                  title="Clear collection scope"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
          </div>

          <label className="flex items-center gap-1.5 rounded-lg border border-surface-200 bg-surface-50 py-1 pl-2.5 pr-2 text-xs font-medium text-surface-600 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-300">
            <span>top-k</span>
            <input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => setTopK(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
              className="w-8 rounded bg-transparent text-center font-mono outline-none"
              title="Chunks retrieved per query"
            />
          </label>

          {activeProvider?.mode === 'cloud' && (
            <span
              className="flex items-center gap-1.5 rounded-lg border border-sky-200 bg-sky-50 py-1 px-2.5 text-xs font-medium text-sky-800 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-300 shadow-2xs"
              title={`Cloud Generation Active: Using ${activeProvider.provider} (${activeProvider.model}). Prompts & top-${topK} retrieved passages transmitted via encrypted TLS. Document storage and vector search remain 100% on-premises.`}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-pulse shrink-0" />
              <span className="font-semibold uppercase">{activeProvider.provider}</span>
              <span className="text-[11px] font-mono text-sky-600 dark:text-sky-400">({activeProvider.model})</span>
            </span>
          )}
        </div>

        {/* Staging Shelf: Displays staged attachments with thumbnails & removal controls */}
        {stagedFiles.length > 0 && (
          <div className="flex flex-wrap gap-2.5 p-2.5 rounded-xl border border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850">
            {stagedFiles.map((att) => (
              <div
                key={att.id}
                className="group relative flex items-center gap-2.5 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 p-2 text-xs shadow-subtle max-w-sm"
              >
                {att.type === 'image' && att.previewUrl && (
                  <img
                    src={att.previewUrl}
                    alt={att.file.name}
                    className="h-10 w-10 rounded object-cover border border-surface-200 dark:border-surface-700"
                  />
                )}
                {att.type === 'audio' && (
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-amber-50 text-amber-600 dark:bg-amber-950 dark:text-amber-400">
                    <AudioLines className="h-5 w-5" />
                  </div>
                )}
                {att.type === 'document' && (
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-brand-50 text-brand-600 dark:bg-brand-950 dark:text-brand-400">
                    <FileText className="h-5 w-5" />
                  </div>
                )}

                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-surface-800 dark:text-surface-200">
                    {att.file.name}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[10px] text-surface-400">
                      {formatSize(att.file.size)} &middot; {att.type}
                    </p>
                    {att.type === 'audio' && (
                      <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.2 text-[9px] font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" title="Saved audio file is processed on-premise using local Whisper (/api/transcribe)">
                        <ShieldCheck className="h-2.5 w-2.5" />
                        Local Whisper (Air-Gapped Processing)
                      </span>
                    )}
                  </div>
                  {att.transcribing && (
                    <span className="flex items-center gap-1 text-[10px] text-amber-600 dark:text-amber-400">
                      <Loader2 className="h-2.5 w-2.5 animate-spin" /> Transcribing via local Whisper...
                    </span>
                  )}
                  {att.transcript && (
                    <div className="mt-1 flex items-center gap-1.5">
                      <p className="truncate text-[10px] text-surface-600 dark:text-surface-300 italic max-w-[180px]" title={att.transcript}>
                        "{att.transcript}"
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          setInput(att.transcript || '')
                          textareaRef.current?.focus()
                        }}
                        className="rounded px-1.5 py-0.5 text-[9px] font-medium bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-900/40 dark:text-amber-300"
                        title="Click to load transcript into query box and edit words or add instructions"
                      >
                        Edit in Query
                      </button>
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => removeStaged(att.id)}
                  className="rounded p-1 text-surface-400 hover:text-rose-600 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
                  title={`Remove ${att.file.name}`}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Live Audio Recording Status Banner */}
        {recording && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-600 animate-ping" />
                <span className="font-semibold">Recording Voice Input...</span>
                <span className="font-mono font-medium">({recordingDuration}s)</span>
              </div>
              <button
                type="button"
                onClick={stopRecording}
                className="flex items-center gap-1.5 rounded-lg bg-rose-600 px-3 py-1 text-xs font-semibold text-white hover:bg-rose-700 shadow-xs"
              >
                <StopCircle className="h-3.5 w-3.5" />
                <span>Done Recording</span>
              </button>
            </div>
            {/* Speech Recognition & Offline Privacy Disclosure */}
            <div className="flex items-start gap-2 text-[11px] text-surface-700 dark:text-surface-300 border-t border-rose-200/80 dark:border-rose-900/60 pt-2.5 leading-relaxed bg-white/70 dark:bg-surface-850/70 rounded-lg p-2.5 mt-2">
              <ShieldCheck className="h-4 w-4 shrink-0 mt-0.5 text-brand-600 dark:text-brand-400" />
              <div>
                <p className="font-semibold text-surface-900 dark:text-surface-100">Live Dictation uses Browser Speech Service (Online)</p>
                <p className="text-[10px] text-surface-600 dark:text-surface-400 mt-0.5">
                  Real-time dictation text streams through your browser vendor's recognition engine (Google/Apple cloud). Once you click "Done Recording", the saved audio file is processed 100% locally and privately by on-premises Whisper with zero cloud egress.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Unified Input Box (Contracko / Clara AI style) */}
        <div className="relative flex items-end gap-2 rounded-2xl border border-surface-300 bg-white p-2 shadow-sm focus-within:border-brand-500 focus-within:ring-1 focus-within:ring-brand-500 dark:border-surface-700 dark:bg-surface-800">
          {/* Attachment Paperclip Button & Menu */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex h-9 w-9 items-center justify-center rounded-xl text-surface-500 hover:bg-surface-100 hover:text-surface-800 dark:text-surface-400 dark:hover:bg-surface-700 dark:hover:text-surface-200 transition-colors"
              title="Attach document, image, or audio"
            >
              <Paperclip className="h-4 w-4" />
            </button>

            {menuOpen && (
              <div
                className="absolute bottom-11 left-0 z-30 w-44 rounded-xl border border-surface-200 bg-white p-1.5 shadow-elevated dark:border-surface-700 dark:bg-surface-850 text-xs"
                onClick={() => setMenuOpen(false)}
              >
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 hover:bg-surface-100 dark:hover:bg-surface-700 text-left"
                >
                  <FileText className="h-4 w-4 text-brand-600" />
                  <span>Document (PDF/Office)</span>
                </button>
                <button
                  type="button"
                  onClick={() => imageInputRef.current?.click()}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 hover:bg-surface-100 dark:hover:bg-surface-700 text-left"
                >
                  <ImageIcon className="h-4 w-4 text-sky-600" />
                  <span>Image (PNG/JPG)</span>
                </button>
                <button
                  type="button"
                  onClick={() => audioInputRef.current?.click()}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 hover:bg-surface-100 dark:hover:bg-surface-700 text-left"
                >
                  <AudioLines className="h-4 w-4 text-amber-600" />
                  <span>Audio File</span>
                </button>
              </div>
            )}
          </div>

          {/* Voice Record Mic Button */}
          {!recording ? (
            <button
              type="button"
              onClick={startRecording}
              className="flex h-9 w-9 items-center justify-center rounded-xl text-surface-500 hover:bg-surface-100 hover:text-surface-800 dark:text-surface-400 dark:hover:bg-surface-700 dark:hover:text-surface-200 transition-colors"
              title="Record voice instruction"
            >
              <Mic className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={stopRecording}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-rose-100 text-rose-600 dark:bg-rose-950 dark:text-rose-400 animate-pulse"
              title="Stop recording"
            >
              <StopCircle className="h-4 w-4" />
            </button>
          )}

          {/* Hidden File Inputs */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={SUPPORTED_DOCS}
            data-testid="composer-file-input"
            className="hidden"
            onChange={(e) => {
              Array.from(e.target.files || []).forEach(stageFile)
              e.target.value = ''
            }}
          />
          <input
            ref={imageInputRef}
            type="file"
            accept={SUPPORTED_IMAGES}
            data-testid="composer-image-input"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) stageFile(f)
              e.target.value = ''
            }}
          />
          <input
            ref={audioInputRef}
            type="file"
            accept={SUPPORTED_AUDIO}
            data-testid="composer-audio-input"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) stageFile(f)
              e.target.value = ''
            }}
          />

          {/* Textarea Input Area */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              stagedFiles.length > 0
                ? 'Enter custom question or instruction for this attachment...'
                : 'Ask a question in any language (English, Hindi, Spanish, etc.)...'
            }
            className="scroll-thin max-h-44 min-h-[38px] flex-1 resize-none bg-transparent py-2 px-1 text-sm text-surface-900 placeholder:text-surface-400 focus:outline-none dark:text-surface-100 dark:placeholder:text-surface-500"
          />

          {/* Send or Stop Generation Button */}
          {busy ? (
            <button
              type="button"
              onClick={handleSubmit}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-rose-600 text-white shadow-sm hover:bg-rose-700 transition-colors"
              title="Stop response generation"
            >
              <Square className="h-4 w-4 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => handleSubmit()}
              disabled={!input.trim() && stagedFiles.length === 0}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm hover:bg-brand-700 disabled:opacity-30 disabled:pointer-events-none transition-colors"
              title="Send message (Enter)"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
