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
  prefillQuery?: string
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
  activeProvider: _activeProvider,
  prefillQuery,
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
  const recorderMimeRef = useRef<string>('audio/webm')
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<any>(null)
  const speechRecRef = useRef<any>(null)
  const isRecordingRef = useRef<boolean>(false)
  const initialPromptRef = useRef<string>('')
  const accumulatedSpeechRef = useRef<string>('')
  const lastSessionFinalRef = useRef<string>('')
  const isSubmittingRef = useRef<boolean>(false)
  const querySentRef = useRef<boolean>(false)
  const hasLiveDictatedRef = useRef<boolean>(false)
  const inputRef = useRef<string>('')
  const recordingSessionIdRef = useRef<number>(0)

  // Keep inputRef constantly updated with input state to prevent stale closures
  useEffect(() => {
    inputRef.current = input
  }, [input])

  // Listen for query rewrite/edit triggers
  useEffect(() => {
    if (prefillQuery !== undefined && prefillQuery !== '') {
      inputRef.current = prefillQuery
      setInput(prefillQuery)
      if (textareaRef.current) {
        textareaRef.current.focus()
      }
    }
  }, [prefillQuery])

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
          // Background transcript saved on attachment chip (available via 'Edit in Query' button)
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

  // Helper to obtain audio media stream across browsers
  async function getAudioMediaStream(): Promise<MediaStream> {
    if (navigator?.mediaDevices?.getUserMedia) {
      try {
        return await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: true,
          },
        })
      } catch {
        return await navigator.mediaDevices.getUserMedia({ audio: true })
      }
    }

    const legacyGetUserMedia =
      (navigator as any)?.getUserMedia ||
      (navigator as any)?.webkitGetUserMedia ||
      (navigator as any)?.mozGetUserMedia ||
      (navigator as any)?.msGetUserMedia

    if (legacyGetUserMedia) {
      return new Promise<MediaStream>((resolve, reject) => {
        legacyGetUserMedia.call(navigator, { audio: true }, resolve, reject)
      })
    }

    throw new Error('NO_GETUSERMEDIA')
  }

  // Live Speech Recognition Helper
  function startLiveSpeechRecognition() {
    if (typeof window === 'undefined') return
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRec) {
      console.warn('[Composer] Web Speech API not supported in this browser.')
      return
    }

    try {
      if (speechRecRef.current) {
        try { speechRecRef.current.stop() } catch {}
        speechRecRef.current = null
      }

      const rec = new SpeechRec()
      rec.continuous = true
      rec.interimResults = true
      rec.lang = navigator.language || 'en-US'

      rec.onresult = (evt: any) => {
        // Discard lingering events if query was submitted or recording stopped
        if (isSubmittingRef.current || querySentRef.current || !isRecordingRef.current) {
          return
        }

        let sessionFinal = ''
        let sessionInterim = ''

        for (let i = 0; i < evt.results.length; ++i) {
          const res = evt.results[i]
          if (res.isFinal) {
            sessionFinal += res[0].transcript + ' '
          } else {
            sessionInterim += res[0].transcript
          }
        }

        lastSessionFinalRef.current = sessionFinal.trim()
        const currentLive = [
          accumulatedSpeechRef.current,
          sessionFinal.trim(),
          sessionInterim.trim(),
        ]
          .filter(Boolean)
          .join(' ')
          .trim()

        if (currentLive) {
          const prefix = initialPromptRef.current ? initialPromptRef.current + ' ' : ''
          const full = prefix + currentLive
          hasLiveDictatedRef.current = true
          inputRef.current = full
          setInput(full)
          if (textareaRef.current) {
            textareaRef.current.scrollTop = textareaRef.current.scrollHeight
          }
        }
      }

      rec.onend = () => {
        speechRecRef.current = null
        if (lastSessionFinalRef.current) {
          accumulatedSpeechRef.current = [
            accumulatedSpeechRef.current,
            lastSessionFinalRef.current,
          ]
            .filter(Boolean)
            .join(' ')
            .trim()
          lastSessionFinalRef.current = ''
        }
        // Auto-resume recognition if user is still recording and query not submitted
        if (isRecordingRef.current && !isSubmittingRef.current && !querySentRef.current) {
          setTimeout(() => {
            if (isRecordingRef.current && !speechRecRef.current && !isSubmittingRef.current && !querySentRef.current) {
              startLiveSpeechRecognition()
            }
          }, 40)
        }
      }

      rec.onerror = (e: any) => {
        if (e?.error === 'no-speech') return
        if (e?.error === 'not-allowed') {
          onError('Microphone is disabled in browser permissions.')
          return
        }
        console.warn('[Composer] Live dictation notice:', e?.error || e)
      }

      rec.start()
      speechRecRef.current = rec
    } catch (err) {
      console.warn('[Composer] Speech recognition init note:', err)
    }
  }

  // Audio Capture for Whisper Backend Fallback
  async function initAudioMediaCapture() {
    try {
      const stream = await getAudioMediaStream()
      streamRef.current = stream
      chunksRef.current = []

      let chosenMime = ''
      const candidateMimes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
        'audio/aac',
      ]
      for (const mime of candidateMimes) {
        if (typeof MediaRecorder !== 'undefined' && typeof MediaRecorder.isTypeSupported === 'function') {
          if (MediaRecorder.isTypeSupported(mime)) {
            chosenMime = mime
            break
          }
        }
      }
      recorderMimeRef.current = chosenMime || 'audio/webm'

      const recorder = chosenMime
        ? new MediaRecorder(stream, { mimeType: chosenMime })
        : new MediaRecorder(stream)

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }
      recorder.onstop = handleRecordingStop

      // Timeslice of 250ms ensures chunks are pushed continuously
      recorder.start(250)
      recorderRef.current = recorder
    } catch (err: any) {
      console.warn('[Composer] MediaRecorder init note:', err)
      const errName = err?.name || ''
      const hasSpeechRec =
        typeof window !== 'undefined' &&
        Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
      if (!hasSpeechRec) {
        if (errName === 'NotAllowedError' || errName === 'PermissionDeniedError') {
          onError('Microphone is disabled in browser permissions.')
        } else if (errName === 'NotFoundError') {
          onError('Microphone device not found.')
        }
      }
    }
  }

  // Voice recording with live speech-to-text review
  function startRecording() {
    if (busy) {
      onError('Please wait for the current response to finish before speaking.')
      return
    }

    if (typeof window !== 'undefined' && window.isSecureContext === false) {
      onError('Microphone requires a secure connection (localhost or HTTPS).')
      return
    }

    recordingSessionIdRef.current += 1
    isRecordingRef.current = true
    querySentRef.current = false
    isSubmittingRef.current = false
    hasLiveDictatedRef.current = false
    initialPromptRef.current = (inputRef.current || input).trim()
    accumulatedSpeechRef.current = ''
    lastSessionFinalRef.current = ''
    chunksRef.current = []
    setRecording(true)

    // 1. MUST BE SYNCHRONOUS: Start speech recognition immediately in user click event
    // This guarantees Chrome preserves the user gesture token so words start typing immediately as you speak!
    startLiveSpeechRecognition()

    // 2. Start audio media capture in background as silent fallback
    initAudioMediaCapture()
  }

  function stopRecording() {
    isRecordingRef.current = false
    setRecording(false)

    if (speechRecRef.current) {
      try {
        speechRecRef.current.onresult = null
        speechRecRef.current.onend = null
        speechRecRef.current.onerror = null
        speechRecRef.current.stop()
      } catch {}
      speechRecRef.current = null
    }

    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      try {
        recorderRef.current.stop()
      } catch {}
    } else {
      handleRecordingStop()
    }
  }

  async function handleRecordingStop() {
    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach((t) => t.stop())
      } catch {}
      streamRef.current = null
    }

    const currentSession = recordingSessionIdRef.current
    const mime = recorderMimeRef.current || 'audio/webm'
    const blob = chunksRef.current.length > 0 ? new Blob(chunksRef.current, { type: mime }) : null
    chunksRef.current = []

    // Focus textarea immediately so user sees cursor and can edit or send right away
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus()
        const len = textareaRef.current.value.length
        textareaRef.current.setSelectionRange(len, len)
      }
    }, 30)

    // 1. If user already submitted the query or is submitting:
    // DO ABSOLUTELY NOTHING! Never call Whisper, never toast, never resurrect text!
    if (isSubmittingRef.current || querySentRef.current) {
      return
    }

    // 2. IF LIVE VOICE DETECTION ALREADY TYPED THE TEXT (or text is present in panel):
    // We are COMPLETELY done! The user's spoken words are already in the message panel.
    // Never call Whisper! Never show dots! Never show error toast!
    const currentTextInPanel = (inputRef.current || input).trim()
    if (hasLiveDictatedRef.current || currentTextInPanel.length > 0) {
      return
    }

    // 3. ONLY IF NOTHING was recognized via live speech (e.g. browser has no Web Speech API or was offline):
    // Run Whisper in the background as a fallback.
    if (blob && blob.size > 1000) {
      try {
        const ext = mime.includes('mp4') ? 'mp4' : mime.includes('ogg') ? 'ogg' : 'webm'
        const recordedFile = new File(
          [blob],
          `voice-recording-${Date.now()}.${ext}`,
          { type: mime }
        )
        const text = await transcribeBlob(recordedFile)
        const trimmed = (text || '').trim()

        // Discard dots or noise (must have alphanumeric characters)
        const hasAlphanumeric = /[a-zA-Z0-9\u0900-\u097F]/.test(trimmed)
        if (
          hasAlphanumeric &&
          currentSession === recordingSessionIdRef.current &&
          !isSubmittingRef.current &&
          !querySentRef.current &&
          !inputRef.current.trim()
        ) {
          const prefix = initialPromptRef.current ? initialPromptRef.current + ' ' : ''
          const finalText = prefix + trimmed
          inputRef.current = finalText
          setInput(finalText)
          setTimeout(() => {
            if (textareaRef.current) {
              textareaRef.current.focus()
              const len = textareaRef.current.value.length
              textareaRef.current.setSelectionRange(len, len)
            }
          }, 30)
          return
        }
      } catch (e: any) {
        console.warn('[Composer] Whisper fallback notice:', e)
      }
    }

    // 4. Only if ABSOLUTELY NOTHING was recognized, nothing was submitted, and textarea is empty:
    if (
      currentSession === recordingSessionIdRef.current &&
      !isSubmittingRef.current &&
      !querySentRef.current &&
      !hasLiveDictatedRef.current &&
      !inputRef.current.trim()
    ) {
      onError('Could not detect speech. Please speak into your microphone and try again.')
    }
  }

  // Main Submit Action
  async function handleSubmit(e?: React.FormEvent) {
    if (e) e.preventDefault()
    if (busy) {
      if (onStopGeneration) onStopGeneration()
      return
    }

    // Immediately invalidate and abort any background audio recording or Whisper fallbacks
    recordingSessionIdRef.current += 1
    isRecordingRef.current = false
    setRecording(false)

    if (speechRecRef.current) {
      try {
        speechRecRef.current.onresult = null
        speechRecRef.current.onend = null
        speechRecRef.current.onerror = null
        speechRecRef.current.stop()
      } catch {}
      speechRecRef.current = null
    }

    if (recorderRef.current) {
      try {
        recorderRef.current.onstop = null
        recorderRef.current.ondataavailable = null
        if (recorderRef.current.state !== 'inactive') {
          recorderRef.current.stop()
        }
      } catch {}
      recorderRef.current = null
    }

    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach((t) => t.stop())
      } catch {}
      streamRef.current = null
    }

    chunksRef.current = []
    accumulatedSpeechRef.current = ''
    lastSessionFinalRef.current = ''
    initialPromptRef.current = ''
    hasLiveDictatedRef.current = false
    isSubmittingRef.current = true
    querySentRef.current = true

    const queryText = (inputRef.current || input).trim()
    inputRef.current = ''
    setInput('')

    // Reset submitting lock after safe delay
    setTimeout(() => {
      isSubmittingRef.current = false
    }, 1500)

    // 1. Image staged: execute image query with custom prompt
    const stagedImage = stagedFiles.find((f) => f.type === 'image')
    if (stagedImage) {
      onImageQuery(stagedImage.file, queryText)
      setStagedFiles((prev) => prev.filter((f) => f.id !== stagedImage.id))
      return
    }

    // 2. Audio staged: execute audio query with custom prompt
    const stagedAudio = stagedFiles.find((f) => f.type === 'audio')
    if (stagedAudio) {
      onAudioQuery(stagedAudio.file, queryText)
      setStagedFiles((prev) => prev.filter((f) => f.id !== stagedAudio.id))
      return
    }

    // 3. Document(s) staged: ingest and answer
    const stagedDocs = stagedFiles.filter((f) => f.type === 'document')
    if (stagedDocs.length > 0 && onIngestAndQuery) {
      const docFiles = stagedDocs.map((d) => d.file)
      setStagedFiles((prev) => prev.filter((f) => f.type !== 'document'))
      await onIngestAndQuery(docFiles, queryText || 'Summarize the attached document(s) and highlight main points.')
      return
    }

    // 4. Text query only
    if (!queryText) return
    onSubmitText(queryText)
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
                      <span className="inline-flex items-center gap-1 rounded bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 text-[9px] font-medium text-surface-600 dark:text-surface-300">
                        <AudioLines className="h-2.5 w-2.5 text-brand-600 dark:text-brand-400" />
                        Audio &middot; Local Whisper
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

        {/* Live Audio Recording Indicator */}
        {recording && (
          <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50/80 px-3.5 py-2 text-xs text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200 animate-in fade-in duration-150">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose-500" />
              </span>
              <span className="font-medium">Recording audio...</span>
              <span className="font-mono text-rose-600 dark:text-rose-300">({recordingDuration}s)</span>
            </div>
            <button
              type="button"
              onClick={stopRecording}
              className="flex items-center gap-1.5 rounded-lg bg-rose-600 px-3 py-1 text-xs font-semibold text-white transition hover:bg-rose-700 shadow-sm"
            >
              <StopCircle className="h-3.5 w-3.5" />
              <span>Done</span>
            </button>
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
              disabled={busy}
              className="flex h-9 w-9 items-center justify-center rounded-xl text-surface-500 hover:bg-surface-100 hover:text-surface-800 disabled:opacity-40 disabled:cursor-not-allowed dark:text-surface-400 dark:hover:bg-surface-700 dark:hover:text-surface-200 transition-colors"
              title={busy ? "Generating response..." : "Record voice instruction"}
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
            onChange={(e) => {
              inputRef.current = e.target.value
              setInput(e.target.value)
            }}
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
