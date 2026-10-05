import { useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'
import {
  FileText, Image as ImageIcon, AudioLines, ChevronDown, ChevronRight,
  ExternalLink, Loader2, Play, Library, X, MapPin, Clock, Hash,
} from 'lucide-react'
import type { Citation, Modality, SourceDetail } from '../types'
import { getSource } from '../api'
import { getMediaUrl } from "../api";

function ModalityIcon({ modality, className }: { modality: Modality; className?: string }) {
  if (modality === 'image') return <ImageIcon className={className} />
  if (modality === 'audio') return <AudioLines className={className} />
  return <FileText className={className} />
}

export default function SourcesPanel({
  citations, flashIndex, onError, open, onClose,
}: {
  citations: Citation[]
  flashIndex: number | null
  onError: (msg: string) => void
  open: boolean
  onClose: () => void
}) {
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-sm lg:hidden" onClick={onClose} />}
      <aside className={`scroll-thin fixed inset-y-0 right-0 z-40 flex w-96 max-w-[90vw] transform flex-col overflow-y-auto border-l border-slate-200 bg-white transition-transform duration-300 dark:border-slate-800 dark:bg-slate-900 lg:static lg:z-auto lg:w-96 lg:max-w-none lg:translate-x-0 ${open ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'}`}>
        <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95">
          <Library className="h-4 w-4 text-accent-600" />
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Sources</h2>
          {citations.length > 0 && (
            <span className="ml-auto rounded-full bg-accent-50 px-2 py-0.5 text-xs font-medium text-accent-600 dark:bg-accent-500/15 dark:text-accent-300">{citations.length}</span>
          )}
          <button onClick={onClose} className="ml-1 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 lg:hidden"><X className="h-4 w-4" /></button>
        </div>

        {citations.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center">
            <p className="text-sm text-slate-400">Citations for the latest answer appear here.</p>
          </div>
        ) : (
          <div className="space-y-3 p-4">
            {citations.map((c) => (
              <CitationCard key={`${c.index}-${c.id}`} citation={c} flash={flashIndex === c.index} onError={onError} />
            ))}
          </div>
        )}
      </aside>
    </>
  )
}

function CitationCard({ citation, flash, onError }: { citation: Citation; flash: boolean; onError: (msg: string) => void }) {
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
      try { setDetail(await getSource(citation.id)) }
      catch (err) { onError((err as Error).message); setExpanded(false) }
      finally { setLoading(false) }
    }
  }

  // Quick location label in the card header.
  const locationLabel = citation.timestamp != null ? `@ ${citation.timestamp}`
    : citation.page != null ? `p. ${citation.page}` : citation.source_type

  // brief §19: this is a relative min-max normalization across this
  // answer's own citations, not a calibrated probability — displaying it
  // as unqualified "confidence" would overstate what it means (three
  // near-identical scores could render as 100%/50%/0%). Read the new
  // relative_relevance field; fall back to the deprecated confidence
  // alias only if talking to an older backend that hasn't been updated.
  const relevance = citation.relative_relevance ?? citation.confidence ?? 0
  const relevanceColor = relevance >= 70 ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300'
    : relevance >= 40 ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300'
    : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'

  return (
    <div ref={cardRef} className="rounded-xl border border-slate-200 bg-white transition dark:border-slate-700 dark:bg-slate-800">
      <button onClick={toggle} className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left">
        <span className="mt-0.5 flex h-5 min-w-5 items-center justify-center rounded bg-accent-600 px-1 text-[11px] font-bold text-white">{citation.index}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 text-sm font-medium text-slate-800 dark:text-slate-100">
            <ModalityIcon modality={citation.modality} className="h-4 w-4 shrink-0 text-slate-400" />
            <span className="truncate" title={citation.file}>{citation.file}</span>
            <span className={`ml-auto shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${relevanceColor}`}
                 title="Relevance relative to this answer's other sources — not a calibrated confidence score">{relevance}%</span>
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-[11px] text-slate-400">
            <span className="capitalize">{citation.source_type}</span><span>·</span>
            <span className="font-medium text-accent-600 dark:text-accent-300">{locationLabel}</span>
          </div>
          <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">{citation.snippet}</p>
        </div>
        <span className="mt-0.5 text-slate-400">{expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</span>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 px-3 py-3 dark:border-slate-700">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Loading source…</div>
          ) : detail ? <SourceDetailView detail={detail} audioRef={audioRef} /> : null}
        </div>
      )}
    </div>
  )
}

/** Prominent "where was this found" badge: page / timecode / OCR block. */
function LocationBadge({ detail }: { detail: SourceDetail }) {
  let icon = <MapPin className="h-3.5 w-3.5" />
  let text = ''
  if (detail.modality === 'document' && detail.page != null) {
    text = `Found on page ${detail.page}`
  } else if (detail.modality === 'audio' && detail.timestamp != null) {
    icon = <Clock className="h-3.5 w-3.5" />
    text = `Spoken at ${detail.timestamp}`
  } else if (detail.modality === 'image' && detail.chunk != null) {
    icon = <Hash className="h-3.5 w-3.5" />
    text = `Text block ${detail.chunk + 1}${detail.chunk_total ? ` of ${detail.chunk_total}` : ''}`
  }
  if (!text) return null
  return (
    <div className="mb-1 inline-flex items-center gap-1.5 rounded-lg bg-accent-50 px-2.5 py-1 text-xs font-medium text-accent-700 dark:bg-accent-500/15 dark:text-accent-200">
      {icon} {text}
    </div>
  )
}

function HighlightedText({ text, label }: { text: string; label?: string }) {
  return (
    <div className="scroll-thin max-h-64 overflow-y-auto rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700 dark:bg-slate-900 dark:text-slate-300">
      {label && <span className="font-semibold text-slate-500">{label} </span>}
      <span className="whitespace-pre-wrap">{text}</span>
    </div>
  )
}

function SourceDetailView({ detail, audioRef }: { detail: SourceDetail; audioRef: RefObject<HTMLAudioElement> }) {
  const [mediaUrl, setMediaUrl] = useState("");

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    async function loadMedia() {
      try {
        objectUrl = await getMediaUrl(detail.media_url);
        if (active) setMediaUrl(objectUrl);
      } catch (err) { console.error(err); }
    }
    loadMedia();
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [detail.media_url]);

  if (detail.modality === 'image') {
    return (
      <div className="space-y-2">
        <LocationBadge detail={detail} />
        <img src={mediaUrl} alt={detail.file} className="max-h-64 w-full rounded-lg border border-slate-200 object-contain dark:border-slate-700" />
        {detail.full_text && (
          <HighlightedText text={detail.full_text} label="Text read from image:" />
        )}
        <MediaLink url={mediaUrl} label="Open image" />
      </div>
    )
  }
  if (detail.modality === 'audio') {
    return (
      <div className="space-y-2">
        <LocationBadge detail={detail} />
        <audio ref={audioRef} controls src={mediaUrl} className="w-full">Your browser does not support audio.</audio>
        {detail.start != null && (
          <button
            onClick={() => { const el = audioRef.current; if (!el) return; el.currentTime = detail.start as number; void el.play() }}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-accent-700">
            <Play className="h-3.5 w-3.5" /> Play from {detail.timestamp ?? `${detail.start}s`}
          </button>
        )}
        {detail.full_text && <HighlightedText text={detail.full_text} label="Transcript:" />}
        <MediaLink url={mediaUrl} label="Open audio file" />
      </div>
    )
  }
  return (
    <div className="space-y-2">
      <LocationBadge detail={detail} />
      <HighlightedText text={detail.full_text || '(No extracted text available.)'} />
      <MediaLink url={mediaUrl} label="Open / download original" />
    </div>
  )
}

function MediaLink({ url, label }: { url: string; label: string }) {

  async function openMedia() {
    try {
      const blobUrl = await getMediaUrl(url);
      window.open(blobUrl, "_blank");
    } catch (err) {
      console.error(err);
      alert("Unable to open file.");
    }
  }

  return (
    <button
      onClick={openMedia}
      className="inline-flex items-center gap-1.5 text-xs font-medium text-accent-600 transition hover:text-accent-700 hover:underline"
    >
      <ExternalLink className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}
