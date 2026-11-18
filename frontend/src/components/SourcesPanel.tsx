import { useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'
import {
  FileText,
  Image as ImageIcon,
  AudioLines,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Loader2,
  Library,
  X,
  MapPin,
  Clock,
  Hash,
  Download,
} from 'lucide-react'
import type { Citation, Modality, SourceDetail } from '../types'
import { getSource, getMediaUrl, getToken } from '../api'

function ModalityIcon({ modality, className }: { modality: Modality; className?: string }) {
  if (modality === 'image') return <ImageIcon className={className} />
  if (modality === 'audio') return <AudioLines className={className} />
  return <FileText className={className} />
}

export default function SourcesPanel({
  citations,
  flashIndex,
  onError,
  open,
  onClose,
  onOpenViewer,
}: {
  citations: Citation[]
  flashIndex: number | null
  onError: (msg: string) => void
  open: boolean
  onClose: () => void
  onOpenViewer?: (file: string, citation?: Citation) => void
}) {
  const safeCitations = Array.isArray(citations) ? citations : []

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-surface-950/60 backdrop-blur-xs lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`scroll-thin fixed inset-y-0 right-0 z-40 flex w-96 max-w-[90vw] transform flex-col overflow-y-auto border-l border-surface-200 bg-white transition-transform duration-200 dark:border-surface-800 dark:bg-surface-900 lg:static lg:z-auto lg:w-96 lg:max-w-none lg:translate-x-0 ${
          open ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-surface-200 bg-white/95 px-4 py-3 backdrop-blur dark:border-surface-800 dark:bg-surface-900/95">
          <div className="flex items-center gap-2">
            <Library className="h-4 w-4 text-surface-500" />
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-surface-900 dark:text-surface-100">
              Evidence Sources
            </h2>
            {safeCitations.length > 0 && (
              <span className="rounded bg-surface-100 dark:bg-surface-800 px-1.5 py-0.2 font-mono text-[10px] font-semibold text-surface-600 dark:text-surface-300 border border-surface-200 dark:border-surface-700">
                {safeCitations.length}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 lg:hidden cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {safeCitations.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center font-sans">
            <p className="text-xs text-surface-400">
              Citations for the latest answer will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-3 p-4">
            {safeCitations.map((c) => (
              <CitationCard
                key={`${c.index}-${c.id}`}
                citation={c}
                flash={flashIndex === c.index}
                onError={onError}
                onOpenViewer={onOpenViewer}
              />
            ))}
          </div>
        )}
      </aside>
    </>
  )
}

function CitationCard({
  citation,
  flash,
  onError,
  onOpenViewer,
}: {
  citation: Citation
  flash: boolean
  onError: (msg: string) => void
  onOpenViewer?: (file: string, citation?: Citation) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState<SourceDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const cardRef = useRef<HTMLDivElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

  useEffect(() => {
    if (flash && cardRef.current) {
      cardRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
      cardRef.current.classList.remove('citation-flash')
      void cardRef.current.offsetWidth
      cardRef.current.classList.add('citation-flash')
    }
  }, [flash])

  async function toggle() {
    const next = !expanded
    setExpanded(next)
    if (next && !detail) {
      setLoading(true)
      try {
        setDetail(await getSource(citation.id))
      } catch (err) {
        onError((err as Error).message)
        setExpanded(false)
      } finally {
        setLoading(false)
      }
    }
  }

  const locationLabel =
    citation.timestamp != null
      ? `@ ${citation.timestamp}`
      : citation.page != null
      ? `p. ${citation.page}`
      : citation.source_type

  const relevance = citation.relative_relevance ?? citation.confidence ?? 0
  const relevanceColor =
    relevance >= 70
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
      : relevance >= 40
      ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
      : 'border-surface-200 bg-surface-100 text-surface-600 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-400'

  return (
    <div
      ref={cardRef}
      className="rounded-lg border border-surface-200 bg-white transition dark:border-surface-800 dark:bg-surface-900 shadow-2xs"
    >
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-start gap-2.5 p-3 text-left cursor-pointer"
      >
        <span className="mt-0.5 flex h-5 min-w-5 items-center justify-center rounded bg-surface-900 text-white dark:bg-surface-100 dark:text-surface-950 font-mono text-[11px] font-bold shadow-2xs">
          {citation.index}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-surface-900 dark:text-surface-100">
            <ModalityIcon modality={citation.modality} className="h-3.5 w-3.5 shrink-0 text-surface-400" />
            <span className="truncate font-mono" title={citation.file}>
              {citation.file}
            </span>
            <span
              className={`ml-auto shrink-0 rounded px-1.5 py-0.2 font-mono text-[10px] font-semibold border ${relevanceColor}`}
              title="Relative retrieval score"
            >
              {relevance}%
            </span>
          </div>

          <div className="mt-0.5 flex items-center gap-2 font-mono text-[10px] text-surface-400">
            <span className="capitalize">{citation.source_type}</span>
            <span>·</span>
            <span className="font-semibold text-surface-700 dark:text-surface-300">{locationLabel}</span>
          </div>

          <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-surface-600 dark:text-surface-400">
            {citation.snippet}
          </p>
        </div>

        <span className="mt-0.5 text-surface-400">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-surface-100 p-3 dark:border-surface-800 bg-surface-50/50 dark:bg-surface-950/50">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-surface-400 font-mono">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading source chunk...
            </div>
          ) : detail ? (
            <SourceDetailView
              detail={detail}
              audioRef={audioRef}
              citation={citation}
              onOpenViewer={onOpenViewer}
            />
          ) : null}
        </div>
      )}
    </div>
  )
}

function LocationBadge({ detail }: { detail: SourceDetail }) {
  let icon = <MapPin className="h-3 w-3" />
  let text = ''
  if (detail.modality === 'document' && detail.page != null) {
    text = `Page ${detail.page}`
  } else if (detail.modality === 'audio' && detail.timestamp != null) {
    icon = <Clock className="h-3 w-3" />
    text = `Timecode: ${detail.timestamp}`
  } else if (detail.modality === 'image' && detail.chunk != null) {
    icon = <Hash className="h-3 w-3" />
    text = `Text block ${detail.chunk + 1}${detail.chunk_total ? ` / ${detail.chunk_total}` : ''}`
  }
  if (!text) return null
  return (
    <div className="mb-2 inline-flex items-center gap-1.5 rounded border border-surface-200 dark:border-surface-700 bg-surface-100 dark:bg-surface-800 px-2 py-0.5 text-[11px] font-mono font-medium text-surface-700 dark:text-surface-300">
      {icon} {text}
    </div>
  )
}

function HighlightedText({ text, label }: { text: string; label?: string }) {
  return (
    <div className="scroll-thin max-h-56 overflow-y-auto rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-850 p-2.5 text-xs leading-relaxed text-surface-800 dark:text-surface-200">
      {label && <span className="font-semibold text-surface-500 font-mono block mb-1">{label}</span>}
      <span className="whitespace-pre-wrap">{text}</span>
    </div>
  )
}

function SourceDetailView({
  detail,
  audioRef,
  citation,
  onOpenViewer,
}: {
  detail: SourceDetail
  audioRef: RefObject<HTMLAudioElement>
  citation?: Citation
  onOpenViewer?: (file: string, citation?: Citation) => void
}) {
  const [mediaUrl, setMediaUrl] = useState('')

  useEffect(() => {
    let active = true
    let objectUrl = ''
    async function loadMedia() {
      if (detail.modality !== 'image' && detail.modality !== 'audio') return
      try {
        if (detail.media_url) {
          objectUrl = await getMediaUrl(detail.media_url)
          if (active) setMediaUrl(objectUrl)
        }
      } catch (err) {
        console.error(err)
      }
    }
    loadMedia()
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [detail])

  if (detail.modality === 'image') {
    return (
      <div className="space-y-2.5">
        <LocationBadge detail={detail} />
        <img
          src={mediaUrl || detail.media_url}
          alt={detail.file}
          className="max-h-60 w-full rounded-lg border border-surface-200 object-contain dark:border-surface-700 bg-black/10"
        />
        {detail.full_text && (
          <HighlightedText text={detail.full_text} label="OCR Text Extracted:" />
        )}
      </div>
    )
  }

  if (detail.modality === 'audio') {
    return (
      <div className="space-y-2.5">
        <LocationBadge detail={detail} />
        <audio ref={audioRef} controls src={mediaUrl || detail.media_url} className="w-full">
          Your browser does not support audio.
        </audio>
        {detail.full_text && <HighlightedText text={detail.full_text} label="Whisper Transcript:" />}
      </div>
    )
  }

  return (
    <div className="space-y-2.5">
      <LocationBadge detail={detail} />
      <HighlightedText text={detail.full_text || '(No extracted text available.)'} />
      <div className="flex flex-wrap items-center gap-2 pt-1">
        {onOpenViewer && (detail.file || citation?.file) && (
          <button
            type="button"
            onClick={() => onOpenViewer(detail.file || citation?.file || '', citation)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-100 dark:bg-surface-800 px-2.5 py-1 text-xs font-mono font-medium text-surface-800 dark:text-surface-200 transition hover:bg-surface-200 dark:hover:bg-surface-700 cursor-pointer shadow-2xs"
          >
            <ExternalLink className="h-3 w-3" />
            <span>View in Document Viewer {detail.page != null ? `(p. ${detail.page})` : ''}</span>
          </button>
        )}
        <SafeDownloadButton
          url={mediaUrl || detail.media_url}
          filename={detail.file || citation?.file}
        />
      </div>
    </div>
  )
}

function SafeDownloadButton({
  url,
  filename,
}: {
  url?: string
  filename?: string
}) {
  const [downloading, setDownloading] = useState(false)
  if (!url) return null

  async function handleDownload() {
    setDownloading(true)
    try {
      const token = getToken()
      let targetUrl = url!
      if (!targetUrl.startsWith('http') && !targetUrl.startsWith('/')) {
        targetUrl = '/' + targetUrl
      }
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch(targetUrl, { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = filename || 'document'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(objectUrl)
    } catch (e) {
      console.warn('Direct download fallback:', e)
      const token = getToken()
      const sep = url!.includes('?') ? '&' : '?'
      window.open(`${url}${token ? `${sep}token=${encodeURIComponent(token)}` : ''}`, '_blank')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleDownload}
      disabled={downloading}
      className="inline-flex items-center gap-1.5 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-850 px-2.5 py-1 text-xs font-mono text-surface-600 hover:text-surface-900 dark:text-surface-400 dark:hover:text-surface-200 transition cursor-pointer shadow-2xs"
      title="Download file"
    >
      {downloading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
      <span>Download</span>
    </button>
  )
}
