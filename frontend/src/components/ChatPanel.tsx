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
  Edit3,
} from 'lucide-react'
import type { ChatMessage, Citation } from '../types'
import AnswerText from './AnswerText'
import AuthImage from './AuthImage'
import Lightbox from './Lightbox'
import { Badge } from './ui/Badge'

type LightboxTarget = { mediaUrl?: string; src?: string; alt?: string }

export interface ChatPanelProps {
  messages: ChatMessage[]
  onCitationClick: (index: number, citations?: Citation[], answerText?: string, userQuery?: string) => void
  onPromptClick?: (prompt: string) => void
  onRegenerate?: () => void
  onRewriteQuery?: (query: string) => void
}

export default function ChatPanel({
  messages,
  onCitationClick,
  onPromptClick,
  onRegenerate,
  onRewriteQuery,
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
        {messages.map((m, idx) => {
          if (m.role === 'user') {
            return (
              <UserBubble
                key={m.id || idx}
                message={m}
                onOpenImage={setLightbox}
                onRewrite={onRewriteQuery}
              />
            )
          }
          let precedingUserQuery = ''
          for (let i = idx - 1; i >= 0; i--) {
            if (messages[i].role === 'user') {
              precedingUserQuery = messages[i].text
              break
            }
          }
          return (
            <AssistantBubble
              key={m.id || idx}
              message={m}
              precedingUserQuery={precedingUserQuery}
              onCitationClick={onCitationClick}
              onOpenImage={setLightbox}
              onRegenerate={idx === messages.length - 1 ? onRegenerate : undefined}
            />
          )
        })}
        <div ref={bottomRef} />
      </div>
      {lightbox && <Lightbox {...lightbox} onClose={() => setLightbox(null)} />}
    </div>
  )
}

function UserBubble({
  message,
  onOpenImage,
  onRewrite,
}: {
  message: ChatMessage
  onOpenImage: (t: LightboxTarget) => void
  onRewrite?: (text: string) => void
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="group flex justify-end gap-3 items-start">
      {/* Quick Action buttons (Rewrite/Edit and Copy) */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity self-center text-xs text-surface-400">
        {onRewrite && (
          <button
            type="button"
            onClick={() => onRewrite(message.text)}
            className="flex items-center gap-1 rounded px-2 py-1 bg-surface-100 dark:bg-surface-800 hover:bg-surface-200 dark:hover:bg-surface-700 text-surface-600 dark:text-surface-300 transition shadow-2xs cursor-pointer font-mono text-[11px]"
            title="Edit / Rewrite query"
          >
            <Edit3 className="h-3 w-3 text-brand-500" />
            <span className="hidden sm:inline">EDIT</span>
          </button>
        )}
        <button
          type="button"
          onClick={handleCopy}
          className="rounded p-1 bg-surface-100 dark:bg-surface-800 hover:bg-surface-200 dark:hover:bg-surface-700 text-surface-600 dark:text-surface-300 transition shadow-2xs cursor-pointer"
          title="Copy query text"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>

      <div className="max-w-[85%] sm:max-w-[75%] space-y-2 rounded-xl bg-surface-900 text-surface-50 dark:bg-surface-100 dark:text-surface-950 px-4 py-2.5 text-xs leading-relaxed shadow-subtle border border-surface-800 dark:border-surface-200">
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
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-surface-200 bg-surface-100 text-surface-600 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-300 shadow-2xs font-mono text-xs">
        <User className="h-3.5 w-3.5" />
      </div>
    </div>
  )
}

function AssistantBubble({
  message,
  precedingUserQuery,
  onCitationClick,
  onOpenImage,
  onRegenerate,
}: {
  message: ChatMessage
  precedingUserQuery?: string
  onCitationClick: (index: number, citations?: Citation[], answerText?: string, userQuery?: string) => void
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
    <div className="flex justify-start gap-3 items-start">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-surface-300 bg-surface-900 text-white dark:border-surface-700 dark:bg-surface-800 dark:text-surface-100 shadow-subtle font-mono text-xs">
        <Bot className="h-3.5 w-3.5" />
      </div>

      <div className="max-w-[90%] sm:max-w-[85%] space-y-3 rounded-xl border border-surface-200 bg-white p-5 text-xs shadow-subtle dark:border-surface-800 dark:bg-surface-900">
        {message.loading ? (
          <div className="flex items-center gap-2.5 text-surface-500 dark:text-surface-400 py-1 font-mono text-xs">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-600 dark:text-brand-400" />
            <span>SYNTHESIZING GROUNDED RESPONSE...</span>
          </div>
        ) : (
          <>
            {/* Context Label if present */}
            {message.contextLabel && message.contextValue && (
              <div className="flex items-center gap-2 rounded-lg border border-surface-200 bg-surface-50 px-3 py-2 text-xs text-surface-700 dark:border-surface-800 dark:bg-surface-850 dark:text-surface-300">
                <ImageIcon className="h-3.5 w-3.5 shrink-0 text-brand-600 dark:text-brand-400" />
                <span className="font-semibold">{message.contextLabel}:</span>{' '}
                <span className="truncate font-mono">{message.contextValue}</span>
              </div>
            )}

            {/* Answer Body */}
            <AnswerText
              text={message.text}
              onCitationClick={(idx) => onCitationClick(idx, message.citations, message.text, precedingUserQuery)}
              validIndexes={validIndexes}
            />

            {/* Faithfulness Warning Banner */}
            {message.faithfulnessWarning && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                <span>Response generated without complete source coverage. Verify citations.</span>
              </div>
            )}

            {/* Inline Extracted Citation Images */}
            {message.citations && message.citations.length > 0 && (
              <InlineCitationImages citations={message.citations} onOpenImage={onOpenImage} />
            )}

            {/* Assistant Message Action Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2.5 border-t border-surface-100 dark:border-surface-800/80 text-xs text-surface-400">
              <div className="flex items-center gap-2.5">
                <Badge variant={message.usedLlm ? 'brand' : 'neutral'} size="sm">
                  <Sparkles className="h-3 w-3 mr-1" />
                  {message.usedLlm ? 'LLM Grounded' : 'Direct Field Extraction'}
                </Badge>

                {message.citations && message.citations.length > 0 && (
                  <span className="font-mono text-[11px] text-surface-500">
                    {message.citations.length} cited source(s)
                  </span>
                )}
              </div>

              {/* Action Buttons: Copy, Regenerate, Feedback */}
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleCopy}
                  className="rounded p-1 text-surface-400 hover:text-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800 dark:hover:text-surface-200 transition-colors cursor-pointer"
                  title="Copy answer to clipboard"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                </button>

                {onRegenerate && (
                  <button
                    type="button"
                    onClick={onRegenerate}
                    className="rounded p-1 text-surface-400 hover:text-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800 dark:hover:text-surface-200 transition-colors cursor-pointer"
                    title="Regenerate answer"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => setFeedback('up')}
                  className={`rounded p-1 transition-colors cursor-pointer ${
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
                  className={`rounded p-1 transition-colors cursor-pointer ${
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
      {imageCitations.map((c, idx) => (
        <AuthImage
          key={c.id || `${c.file}-${c.index ?? idx}`}
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
    <div className="flex flex-1 flex-col items-center justify-center p-6 text-center max-w-2xl mx-auto my-auto font-sans">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-surface-200 bg-white text-surface-900 dark:border-surface-800 dark:bg-surface-900 dark:text-surface-100 shadow-subtle font-mono font-bold text-sm">
        <MessageSquareText className="h-6 w-6" />
      </div>

      <h2 className="text-lg font-bold tracking-tight text-surface-900 dark:text-surface-100 font-mono uppercase">
        Enterprise Multimodal Workspace
      </h2>
      <p className="mt-1 text-xs text-surface-500 dark:text-surface-400 leading-relaxed max-w-md">
        Ask queries in English, Hindi, or Spanish. Ingest PDFs, spreadsheets, scans, or recordings. All answers are strictly grounded with verified citations.
      </p>

      {/* Suggestion Cards */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
        {suggestions.map((s, idx) => {
          const Icon = s.icon
          return (
            <div
              key={idx}
              onClick={() => onSelectPrompt && onSelectPrompt(s.desc)}
              className="cursor-pointer rounded-lg border border-surface-200 dark:border-surface-800 bg-white dark:bg-surface-900 p-3 shadow-subtle hover:border-surface-400 dark:hover:border-surface-600 transition-all"
            >
              <div className="flex items-center gap-2 font-medium text-xs text-surface-800 dark:text-surface-200">
                <Icon className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
                <span className="font-mono text-xs">{s.title}</span>
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
