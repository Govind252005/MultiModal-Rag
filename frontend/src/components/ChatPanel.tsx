import { useEffect, useRef, useState } from 'react'
import {
  Bot,
  User,
  MessageSquareText,
  Loader2,
  Sparkles,
  AlertTriangle,
  Copy,
  Check,
  RotateCcw,
  ThumbsUp,
  ThumbsDown,
  FileText,
  Image as ImageIcon,
  AudioLines,
} from 'lucide-react'
import type { ChatMessage, Citation } from '../types'
import AnswerText from './AnswerText'
import AuthImage from './AuthImage'
import Lightbox from './Lightbox'
import { Badge } from './ui/Badge'

type LightboxTarget = { mediaUrl?: string; src?: string; alt?: string }

export interface ChatPanelProps {
  messages: ChatMessage[]
  onCitationClick: (index: number) => void
  onPromptClick?: (prompt: string) => void
  onRegenerate?: () => void
}

export default function ChatPanel({
  messages,
  onCitationClick,
  onPromptClick,
  onRegenerate,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [lightbox, setLightbox] = useState<LightboxTarget | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return <EmptyState onSelectPrompt={onPromptClick} />
  }

  return (
    <div className="scroll-thin flex-1 space-y-6 overflow-y-auto px-4 py-6 sm:px-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {messages.map((m, idx) =>
          m.role === 'user' ? (
            <UserBubble key={m.id || idx} message={m} onOpenImage={setLightbox} />
          ) : (
            <AssistantBubble
              key={m.id || idx}
              message={m}
              onCitationClick={onCitationClick}
              onOpenImage={setLightbox}
              onRegenerate={idx === messages.length - 1 ? onRegenerate : undefined}
            />
          )
        )}
        <div ref={bottomRef} />
      </div>
      {lightbox && <Lightbox {...lightbox} onClose={() => setLightbox(null)} />}
    </div>
  )
}

function UserBubble({
  message,
  onOpenImage,
}: {
  message: ChatMessage
  onOpenImage: (t: LightboxTarget) => void
}) {
  return (
    <div className="flex justify-end gap-3">
      <div className="max-w-[85%] sm:max-w-[75%] space-y-2 rounded-2xl rounded-tr-sm bg-brand-600 px-4 py-3 text-sm text-white shadow-subtle">
        {message.imageUrl && (
          <img
            src={message.imageUrl}
            alt="User attachment"
            onClick={() => onOpenImage({ src: message.imageUrl, alt: 'Query Attachment' })}
            className="max-h-56 w-auto cursor-zoom-in rounded-lg object-contain transition hover:opacity-90 bg-black/20"
          />
        )}
        <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
      </div>
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-200 text-surface-600 dark:bg-surface-800 dark:text-surface-300">
        <User className="h-4 w-4" />
      </div>
    </div>
  )
}

function AssistantBubble({
  message,
  onCitationClick,
  onOpenImage,
  onRegenerate,
}: {
  message: ChatMessage
  onCitationClick: (index: number) => void
  onOpenImage: (t: LightboxTarget) => void
  onRegenerate?: () => void
}) {
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)
  const validIndexes = new Set((message.citations ?? []).map((c) => c.index))

  function handleCopy() {
    navigator.clipboard.writeText(message.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex justify-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-900 text-white dark:bg-brand-600 shadow-subtle">
        <Bot className="h-4 w-4" />
      </div>

      <div className="max-w-[90%] sm:max-w-[85%] space-y-3 rounded-2xl rounded-tl-sm border border-surface-200 bg-white p-5 text-sm shadow-subtle dark:border-surface-800 dark:bg-surface-900">
        {message.loading ? (
          <div className="flex items-center gap-2.5 text-surface-500 dark:text-surface-400 py-1">
            <Loader2 className="h-4 w-4 animate-spin text-brand-600" />
            <span className="text-xs font-medium">Generating grounded response...</span>
          </div>
        ) : (
          <>
            {/* Context Label if present (e.g. Image OCR or Audio Transcript) */}
            {message.contextLabel && message.contextValue && (
              <div className="rounded-lg border border-surface-200 bg-surface-50 p-2.5 text-xs text-surface-700 dark:border-surface-800 dark:bg-surface-850 dark:text-surface-300">
                <span className="font-semibold text-surface-500">{message.contextLabel}:</span>{' '}
                <span className="italic">{message.contextValue}</span>
              </div>
            )}

            {/* Answer Body (Rich Markdown + Code + Tables + Clickable Citations) */}
            <AnswerText
              text={message.text}
              onCitationClick={onCitationClick}
              validIndexes={validIndexes}
            />

            {/* Faithfulness Warning Banner */}
            {message.faithfulnessWarning && (
              <div className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                Response generated without complete source coverage. Verify citations.
              </div>
            )}

            {/* Inline Extracted Citation Images */}
            {message.citations && message.citations.length > 0 && (
              <InlineCitationImages citations={message.citations} onOpenImage={onOpenImage} />
            )}

            {/* Assistant Message Action Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-surface-100 dark:border-surface-800/80 text-xs text-surface-400">
              <div className="flex items-center gap-3">
                <Badge variant={message.usedLlm ? 'brand' : 'neutral'} size="sm">
                  <Sparkles className="h-3 w-3 mr-1" />
                  {message.usedLlm ? 'LLM Grounded' : 'Direct Field Extraction'}
                </Badge>

                {message.citations && message.citations.length > 0 && (
                  <span className="text-surface-500 font-medium">
                    {message.citations.length} cited passage(s)
                  </span>
                )}
              </div>

              {/* Action Buttons: Copy, Regenerate, Feedback */}
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleCopy}
                  className="rounded-lg p-1.5 text-surface-400 hover:text-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800 dark:hover:text-surface-200 transition-colors"
                  title="Copy answer to clipboard"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                </button>

                {onRegenerate && (
                  <button
                    type="button"
                    onClick={onRegenerate}
                    className="rounded-lg p-1.5 text-surface-400 hover:text-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800 dark:hover:text-surface-200 transition-colors"
                    title="Regenerate answer"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => setFeedback('up')}
                  className={`rounded-lg p-1.5 transition-colors ${
                    feedback === 'up'
                      ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40'
                      : 'text-surface-400 hover:text-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800 dark:hover:text-surface-200'
                  }`}
                  title="Accurate response"
                >
                  <ThumbsUp className="h-3.5 w-3.5" />
                </button>

                <button
                  type="button"
                  onClick={() => setFeedback('down')}
                  className={`rounded-lg p-1.5 transition-colors ${
                    feedback === 'down'
                      ? 'text-rose-600 bg-rose-50 dark:bg-rose-950/40'
                      : 'text-surface-400 hover:text-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800 dark:hover:text-surface-200'
                  }`}
                  title="Inaccurate response"
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function InlineCitationImages({
  citations,
  onOpenImage,
}: {
  citations: Citation[]
  onOpenImage: (t: LightboxTarget) => void
}) {
  const imageCitations = citations.filter((c) => c.modality === 'image' && c.media_url)
  if (imageCitations.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2 pt-2">
      {imageCitations.map((c) => (
        <AuthImage
          key={c.id}
          url={c.media_url}
          alt={`[${c.index}] ${c.file}`}
          onClick={() => onOpenImage({ mediaUrl: c.media_url, alt: `[${c.index}] ${c.file}` })}
          className="h-28 w-auto max-w-[200px] cursor-zoom-in rounded-lg border border-surface-200 dark:border-surface-700 object-contain shadow-subtle hover:opacity-90 transition-opacity"
        />
      ))}
    </div>
  )
}

function EmptyState({ onSelectPrompt }: { onSelectPrompt?: (p: string) => void }) {
  const suggestions = [
    {
      title: 'Analyze Financial Summary',
      desc: 'वित्तीय वर्ष 2025 में क्लाउड इन्फ्रास्ट्रक्चर का बजट कितना स्वीकृत हुआ?',
      icon: FileText,
    },
    {
      title: 'Document Intelligence',
      desc: 'What fusion algorithm and constant are used for hybrid retrieval?',
      icon: Sparkles,
    },
    {
      title: 'Multimodal Image Query',
      desc: 'Attach an image to extract diagrams, tables, or OCR text',
      icon: ImageIcon,
    },
    {
      title: 'Audio Meeting Review',
      desc: 'Upload or record speech to synthesize action items',
      icon: AudioLines,
    },
  ]

  return (
    <div className="flex flex-1 flex-col items-center justify-center p-6 text-center max-w-2xl mx-auto my-auto">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-950/60 dark:text-brand-400 shadow-subtle">
        <MessageSquareText className="h-7 w-7" />
      </div>

      <h2 className="text-xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
        Enterprise Multimodal Chat
      </h2>
      <p className="mt-1.5 text-xs text-surface-500 dark:text-surface-400 leading-relaxed max-w-md">
        Ask questions in any language, attach documents, images, or audio clips. Answers are strictly
        grounded with verifiable citations.
      </p>

      {/* Suggestion Cards */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
        {suggestions.map((s, idx) => {
          const Icon = s.icon
          return (
            <div
              key={idx}
              onClick={() => onSelectPrompt && onSelectPrompt(s.desc)}
              className="cursor-pointer rounded-xl border border-surface-200 dark:border-surface-800 bg-white dark:bg-surface-900 p-3.5 shadow-subtle hover:border-brand-300 dark:hover:border-brand-700 hover:shadow-card transition-all"
            >
              <div className="flex items-center gap-2 font-semibold text-xs text-surface-800 dark:text-surface-200">
                <Icon className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
                <span>{s.title}</span>
              </div>
              <p className="mt-1 text-[11px] text-surface-500 dark:text-surface-400 line-clamp-2">
                {s.desc}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
