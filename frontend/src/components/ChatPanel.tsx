import { useEffect, useRef, useState } from 'react'
import { Bot, User, MessageSquareText, Loader2, Sparkles, AlertTriangle } from 'lucide-react'
import type { ChatMessage, Citation } from '../types'
import AnswerText from './AnswerText'
import AuthImage from './AuthImage'
import Lightbox from './Lightbox'

/** What the popup should display: an authed media URL or a plain src. */
type LightboxTarget = { mediaUrl?: string; src?: string; alt?: string }

export default function ChatPanel({
  messages, onCitationClick,
}: {
  messages: ChatMessage[]
  onCitationClick: (index: number) => void
}) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [lightbox, setLightbox] = useState<LightboxTarget | null>(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  if (messages.length === 0) return <EmptyState />

  return (
    <div className="scroll-thin flex-1 space-y-6 overflow-y-auto px-4 py-6 sm:px-6">
      {messages.map((m) =>
        m.role === 'user'
          ? <UserBubble key={m.id} text={m.text} imageUrl={m.imageUrl} onOpenImage={setLightbox} />
          : <AssistantBubble key={m.id} message={m} onCitationClick={onCitationClick} onOpenImage={setLightbox} />,
      )}
      <div ref={bottomRef} />
      {lightbox && <Lightbox {...lightbox} onClose={() => setLightbox(null)} />}
    </div>
  )
}

function UserBubble({
  text, imageUrl, onOpenImage,
}: {
  text: string
  imageUrl?: string
  onOpenImage: (t: LightboxTarget) => void
}) {
  return (
    <div className="flex justify-end gap-3">
      <div className="max-w-[85%] space-y-2 rounded-2xl rounded-tr-sm bg-accent-600 px-4 py-2.5 text-sm text-white shadow-sm">
        {imageUrl && (
          <img
            src={imageUrl}
            alt="query image"
            onClick={() => onOpenImage({ src: imageUrl, alt: 'Your query image' })}
            className="max-h-48 w-auto cursor-zoom-in rounded-lg object-contain transition hover:opacity-90"
          />
        )}
        <p className="whitespace-pre-wrap leading-relaxed">{text}</p>
      </div>
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-300">
        <User className="h-4 w-4" />
      </div>
    </div>
  )
}

function InlineCitationImages({
  citations, onOpenImage,
}: {
  citations: Citation[]
  onOpenImage: (t: LightboxTarget) => void
}) {
  const imageCitations = citations.filter(
    (c) => c.modality === 'image' && c.media_url,
  )
  if (imageCitations.length === 0) return null
  return (
    <div className="flex flex-wrap gap-2 pt-1">
      {imageCitations.map((c) => (
        <AuthImage
          key={c.id}
          url={c.media_url}
          alt={`[${c.index}] ${c.file}`}
          onClick={() => onOpenImage({ mediaUrl: c.media_url, alt: `[${c.index}] ${c.file}` })}
          className="h-32 w-auto max-w-[200px] cursor-zoom-in rounded-lg border border-slate-200 object-contain shadow-sm transition hover:opacity-90 dark:border-slate-700"
        />
      ))}
    </div>
  )
}

function AssistantBubble({
  message, onCitationClick, onOpenImage,
}: {
  message: ChatMessage
  onCitationClick: (index: number) => void
  onOpenImage: (t: LightboxTarget) => void
}) {
  const validIndexes = new Set((message.citations ?? []).map((c) => c.index))
  return (
    <div className="flex justify-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent-500 to-accent-700 text-white">
        <Bot className="h-4 w-4" />
      </div>
      <div className="max-w-[85%] space-y-2 rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800">
        {message.loading ? (
          <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin" /><span>Thinking…</span>
          </div>
        ) : (
          <>
            {message.contextLabel && message.contextValue && (
              <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                <span className="font-semibold text-slate-500">{message.contextLabel}:</span>{' '}
                <span className="italic">{message.contextValue}</span>
              </div>
            )}
            <AnswerText text={message.text} onCitationClick={onCitationClick} validIndexes={validIndexes} />
            {message.faithfulnessWarning && (
              <div className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
                <AlertTriangle className="h-3 w-3 shrink-0" />
                Answer may not cite sources directly
              </div>
            )}
            {message.citations && message.citations.length > 0 && (
              <InlineCitationImages citations={message.citations} onOpenImage={onOpenImage} />
            )}
            <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-slate-400">
              <span className="inline-flex items-center gap-1">
                <Sparkles className="h-3 w-3" />
                {message.usedLlm ? 'LLM answer' : 'Extractive (no LLM)'}
              </span>
              {message.citations && message.citations.length > 0 && <span>· {message.citations.length} source(s)</span>}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-50 text-accent-500 dark:bg-accent-500/15">
        <MessageSquareText className="h-8 w-8" />
      </div>
      <h2 className="text-lg font-semibold text-slate-700 dark:text-slate-200">Ask anything about your library</h2>
      <p className="mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">
        Open <span className="font-medium">Library</span> to add files to this chat, then type a question,
        speak with the mic, or query with an image or audio clip. Each chat keeps its own files and history.
      </p>
    </div>
  )
}
