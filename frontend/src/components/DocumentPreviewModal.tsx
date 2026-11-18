import React, { useState, useEffect, useRef, useMemo } from 'react'
import {
  X,
  Maximize2,
  Minimize2,
  Download,
  ExternalLink,
  Play,
  Pause,
  Volume2,
  VolumeX,
  FastForward,
  Rewind,
  ZoomIn,
  ZoomOut,
  FileText,
  Image as ImageIcon,
  Music,
  FileSpreadsheet,
  ChevronLeft,
  ChevronRight,
  Copy,
  Check,
  Search,
  Loader2,
  AlertCircle,
  FileCode,
  Sparkles,
} from 'lucide-react'
import type { DocumentContentResponse } from '../types'
import { getDocumentContent, getToken } from '../api'

export interface DocumentPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  filename: string
  sessionId?: string
  initialPage?: number
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return ''
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

export const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({
  isOpen,
  onClose,
  filename,
  sessionId = 'default',
  initialPage = 1,
}) => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [docContent, setDocContent] = useState<DocumentContentResponse | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [activeTab, setActiveTab] = useState<'preview' | 'text' | 'metadata'>('preview')
  const [copied, setCopied] = useState(false)

  // PDF & Page Navigation State
  const [currentPage, setCurrentPage] = useState<number>(initialPage)
  const [pageInput, setPageInput] = useState<string>(String(initialPage))
  const [pageTextSearch, setPageTextSearch] = useState('')

  // Spreadsheet State
  const [activeSheetIdx, setActiveSheetIdx] = useState(0)

  // Image Zoom State
  const [imgZoom, setImgZoom] = useState(100)

  // Audio Player State
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1.0)

  // Reset & fetch document content when modal opens or target changes
  useEffect(() => {
    if (!isOpen || !filename) return

    let canceled = false
    setLoading(true)
    setError(null)
    setCurrentPage(initialPage || 1)
    setPageInput(String(initialPage || 1))
    setImgZoom(100)
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
    setActiveTab('preview')

    getDocumentContent(sessionId, filename)
      .then((data) => {
        if (canceled) return
        setDocContent(data)
        setLoading(false)
        if (initialPage && initialPage > 1) {
          setCurrentPage(initialPage)
          setPageInput(String(initialPage))
        }
      })
      .catch((err) => {
        if (canceled) return
        setError(err.message || 'Failed to load document content.')
        setLoading(false)
      })

    return () => {
      canceled = true
    }
  }, [isOpen, filename, sessionId, initialPage])

  // Handle ESC key and keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  // Compute authenticated media URL
  const mediaUrl = useMemo(() => {
    if (!docContent?.raw_url) return ''
    const token = getToken()
    const delimiter = docContent.raw_url.includes('?') ? '&' : '?'
    return token ? `${docContent.raw_url}${delimiter}token=${encodeURIComponent(token)}` : docContent.raw_url
  }, [docContent?.raw_url])

  // Compute total pages
  const totalPages = useMemo(() => {
    if (!docContent) return 1
    if (docContent.page_count && docContent.page_count > 0) return docContent.page_count
    if (docContent.pages && docContent.pages.length > 0) return docContent.pages.length
    if (docContent.sheets && docContent.sheets.length > 0) return docContent.sheets.length
    return 1
  }, [docContent])

  // Audio event listeners
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onPlay = () => setIsPlaying(true)
    const onPause = () => setIsPlaying(false)
    const onTimeUpdate = () => setCurrentTime(audio.currentTime)
    const onLoadedMetadata = () => {
      setDuration(audio.duration || 0)
    }
    const onEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
    }

    audio.addEventListener('play', onPlay)
    audio.addEventListener('pause', onPause)
    audio.addEventListener('timeupdate', onTimeUpdate)
    audio.addEventListener('loadedmetadata', onLoadedMetadata)
    audio.addEventListener('ended', onEnded)

    return () => {
      audio.removeEventListener('play', onPlay)
      audio.removeEventListener('pause', onPause)
      audio.removeEventListener('timeupdate', onTimeUpdate)
      audio.removeEventListener('loadedmetadata', onLoadedMetadata)
      audio.removeEventListener('ended', onEnded)
    }
  }, [docContent])

  // Playback control helpers
  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) {
      audio.pause()
    } else {
      audio.play().catch(() => {})
    }
  }

  const handleSeek = (newTime: number) => {
    const audio = audioRef.current
    if (!audio) return
    audio.currentTime = newTime
    setCurrentTime(newTime)
  }

  const handleSkip = (deltaSeconds: number) => {
    const audio = audioRef.current
    if (!audio) return
    const target = Math.min(Math.max(0, audio.currentTime + deltaSeconds), duration || 1000)
    audio.currentTime = target
    setCurrentTime(target)
  }

  const handleVolumeChange = (newVol: number) => {
    const audio = audioRef.current
    setVolume(newVol)
    setIsMuted(newVol === 0)
    if (audio) {
      audio.volume = newVol
      audio.muted = newVol === 0
    }
  }

  const toggleMute = () => {
    const audio = audioRef.current
    if (!audio) return
    const nextMuted = !isMuted
    setIsMuted(nextMuted)
    audio.muted = nextMuted
  }

  const handleSpeedChange = (rate: number) => {
    const audio = audioRef.current
    setPlaybackRate(rate)
    if (audio) {
      audio.playbackRate = rate
    }
  }

  const copyText = (text: string) => {
    if (!text) return
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Modality helper
  const modality = docContent?.modality || (filename.match(/\.(pdf|png|jpg|jpeg|webp|mp3|wav|m4a|xlsx|csv|docx|pptx|cpp|py|txt)$/i)?.[1]?.toLowerCase() as any) || 'text'
  const isPdf = modality === 'pdf' || filename.toLowerCase().endsWith('.pdf')
  const isImage = modality === 'image' || /\.(png|jpe?g|webp|gif|bmp|svg)$/i.test(filename)
  const isAudio = modality === 'audio' || /\.(mp3|wav|m4a|flac|ogg|aac)$/i.test(filename)
  const isSheet = modality === 'xlsx' || /\.(xlsx|xls|csv)$/i.test(filename)
  const isDocx = modality === 'docx' || /\.(docx|doc)$/i.test(filename)
  const isCode = /\.(cpp|cc|c|h|hpp|py|js|jsx|ts|tsx|json|sql|html|css|sh|bat|md)$/i.test(filename)

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 md:p-6 animate-in fade-in duration-200">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-surface-950/80 backdrop-blur-md transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Main Modal Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        className={`relative z-10 flex flex-col bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 shadow-2xl overflow-hidden transition-all duration-300 ${
          isFullscreen
            ? 'fixed inset-0 w-screen h-screen rounded-none'
            : 'w-full max-w-6xl h-[92vh] max-h-[950px] rounded-2xl'
        }`}
      >
        {/* Header Bar */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-3.5 border-b border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850 shrink-0 gap-3">
          {/* File Title & Info */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2 rounded-xl bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 shadow-xs shrink-0">
              {isPdf ? (
                <FileText className="h-5 w-5 text-rose-500" />
              ) : isImage ? (
                <ImageIcon className="h-5 w-5 text-sky-500" />
              ) : isAudio ? (
                <Music className="h-5 w-5 text-purple-500" />
              ) : isSheet ? (
                <FileSpreadsheet className="h-5 w-5 text-emerald-500" />
              ) : isCode ? (
                <FileCode className="h-5 w-5 text-amber-500" />
              ) : (
                <FileText className="h-5 w-5 text-brand-500" />
              )}
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-sm sm:text-base text-surface-900 dark:text-surface-100 truncate max-w-xs sm:max-w-md md:max-w-lg" title={filename}>
                  {filename}
                </h3>
                <span className="hidden sm:inline-flex px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase bg-surface-200 text-surface-700 dark:bg-surface-800 dark:text-surface-300">
                  {modality}
                </span>
              </div>
              <p className="text-xs text-surface-500 dark:text-surface-400 truncate">
                {docContent?.file_size ? `${formatBytes(docContent.file_size)} • ` : ''}
                {isPdf && totalPages ? `${totalPages} page(s) • ` : ''}
                Preview & Document Inspector
              </p>
            </div>
          </div>

          {/* View Tabs (when available) */}
          <div className="hidden md:flex items-center gap-1 bg-surface-200/70 dark:bg-surface-800 p-1 rounded-xl text-xs font-medium">
            <button
              onClick={() => setActiveTab('preview')}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'preview'
                  ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 shadow-xs'
                  : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200'
              }`}
            >
              {isPdf ? 'Full PDF' : isImage ? 'Image View' : isAudio ? 'Audio Player' : isSheet ? 'Spreadsheet' : 'Preview'}
            </button>
            {(isPdf || isDocx || isAudio || (isImage && (docContent?.caption || docContent?.ocr_text))) && (
              <button
                onClick={() => setActiveTab('text')}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  activeTab === 'text'
                    ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 shadow-xs'
                    : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200'
                }`}
              >
                {isAudio ? 'Transcript' : isImage ? 'AI Caption & OCR' : 'Extracted Text'}
              </button>
            )}
          </div>

          {/* Action Toolbar */}
          <div className="flex items-center gap-1.5 shrink-0">
            {mediaUrl && (
              <a
                href={mediaUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 rounded-lg text-surface-600 hover:text-surface-900 hover:bg-surface-200/60 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-800 transition"
                title="Open raw file in new browser tab"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            )}

            <a
              href={`/api/documents/${encodeURIComponent(sessionId)}/${encodeURIComponent(filename)}/download`}
              download={filename}
              className="p-2 rounded-lg text-surface-600 hover:text-surface-900 hover:bg-surface-200/60 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-800 transition"
              title="Download original file"
            >
              <Download className="h-4 w-4" />
            </a>

            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="p-2 rounded-lg text-surface-600 hover:text-surface-900 hover:bg-surface-200/60 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-800 transition"
              title={isFullscreen ? 'Restore standard window' : 'Full screen'}
            >
              {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </button>

            <button
              onClick={onClose}
              className="p-2 rounded-lg text-surface-500 hover:text-surface-900 hover:bg-surface-200 dark:text-surface-400 dark:hover:text-surface-100 dark:hover:bg-surface-800 transition ml-1 cursor-pointer"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-hidden relative flex flex-col bg-surface-100/50 dark:bg-surface-950">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-surface-500">
              <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
              <p className="text-sm font-medium">Loading document preview...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center max-w-md mx-auto">
              <div className="p-3 rounded-full bg-red-100 dark:bg-red-950/50 text-red-600 mb-3">
                <AlertCircle className="h-8 w-8" />
              </div>
              <h4 className="font-semibold text-surface-900 dark:text-surface-100 mb-1">
                Unable to load preview
              </h4>
              <p className="text-xs text-surface-500 mb-4">{error}</p>
              {mediaUrl && (
                <a
                  href={mediaUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 rounded-xl bg-brand-600 text-white text-xs font-semibold shadow hover:bg-brand-700 transition"
                >
                  Download or Open Directly
                </a>
              )}
            </div>
          ) : (
            <>
              {/* 1. PDF DOCUMENT PREVIEW */}
              {isPdf && (
                activeTab === 'preview' ? (
                  <div className="flex flex-col h-full">
                    {/* PDF Sub-Header Controls */}
                    <div className="flex flex-wrap items-center justify-between px-4 py-2 bg-white dark:bg-surface-900 border-b border-surface-200 dark:border-surface-800 text-xs text-surface-600 dark:text-surface-400 gap-2">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            const prev = Math.max(1, currentPage - 1)
                            setCurrentPage(prev)
                            setPageInput(String(prev))
                          }}
                          disabled={currentPage <= 1}
                          className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-800 disabled:opacity-40"
                          title="Previous page"
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </button>
                        <span className="flex items-center gap-1 font-mono">
                          Page{' '}
                          <input
                            type="number"
                            min={1}
                            max={totalPages}
                            value={pageInput}
                            onChange={(e) => setPageInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                const val = parseInt(pageInput, 10)
                                if (!isNaN(val) && val >= 1 && val <= totalPages) {
                                  setCurrentPage(val)
                                }
                              }
                            }}
                            className="w-12 text-center rounded border border-surface-300 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 px-1 py-0.5 text-xs font-mono"
                          />
                          of {totalPages}
                        </span>
                        <button
                          onClick={() => {
                            const next = Math.min(totalPages, currentPage + 1)
                            setCurrentPage(next)
                            setPageInput(String(next))
                          }}
                          disabled={currentPage >= totalPages}
                          className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-800 disabled:opacity-40"
                          title="Next page"
                        >
                          <ChevronRight className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => setActiveTab('text')}
                          className="text-brand-600 hover:text-brand-700 dark:text-brand-400 font-medium underline"
                        >
                          View Extracted Text ({docContent?.pages?.length || 0} pages)
                        </button>
                        <a
                          href={`${mediaUrl}#page=${currentPage}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-surface-500 hover:text-surface-800 dark:hover:text-surface-200 flex items-center gap-1"
                        >
                          Open in external viewer &rarr;
                        </a>
                      </div>
                    </div>

                    {/* PDF Object & IFrame Container */}
                    <div className="flex-1 w-full h-full relative bg-surface-200 dark:bg-surface-950">
                      <object
                        key={`pdf-preview-${filename}-${currentPage}`}
                        data={`${mediaUrl}#page=${currentPage}&toolbar=1&navpanes=1`}
                        type="application/pdf"
                        className="w-full h-full border-0"
                        title={filename}
                      >
                        <iframe
                          key={`pdf-iframe-${filename}-${currentPage}`}
                          src={`${mediaUrl}#page=${currentPage}`}
                          title={filename}
                          className="w-full h-full border-0"
                        >
                          <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                            <p className="text-sm text-surface-600 dark:text-surface-300 mb-3">
                              Your browser does not support inline PDF viewing.
                            </p>
                            <a
                              href={mediaUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 rounded-xl bg-brand-600 text-white text-xs font-semibold shadow hover:bg-brand-700 transition"
                            >
                              Open PDF Document in New Tab
                            </a>
                          </div>
                        </iframe>
                      </object>
                    </div>
                  </div>
                ) : (
                  /* Extracted PDF Text Tab */
                  <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-surface-900">
                    <div className="flex items-center justify-between p-3 border-b border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850 gap-3">
                      <div className="relative flex-1 max-w-sm">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-surface-400" />
                        <input
                          type="text"
                          placeholder="Search in extracted text..."
                          value={pageTextSearch}
                          onChange={(e) => setPageTextSearch(e.target.value)}
                          className="w-full pl-8 pr-3 py-1 rounded-lg text-xs border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            const curPageData = docContent?.pages?.find((p) => p.page_number === currentPage)
                            copyText(curPageData?.text || '')
                          }}
                          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium border border-surface-200 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800"
                        >
                          {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                          {copied ? 'Copied Page' : 'Copy Page Text'}
                        </button>
                      </div>
                    </div>

                    <div className="flex-1 overflow-y-auto p-6 font-sans text-sm leading-relaxed text-surface-800 dark:text-surface-200 whitespace-pre-wrap">
                      {(() => {
                        const pageData = docContent?.pages?.find((p) => p.page_number === currentPage)
                        const fullText = pageData?.text || docContent?.content || 'No text extracted for this page.'
                        if (!pageTextSearch.trim()) return fullText
                        const q = pageTextSearch.trim().toLowerCase()
                        const parts = fullText.split(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'))
                        return parts.map((part, i) =>
                          part.toLowerCase() === q ? (
                            <mark key={i} className="bg-amber-300 text-amber-950 dark:bg-amber-400 dark:text-amber-950 px-0.5 rounded font-medium">
                              {part}
                            </mark>
                          ) : (
                            part
                          )
                        )
                      })()}
                    </div>
                  </div>
                )
              )}

              {/* 2. IMAGE PREVIEW */}
              {isImage && (
                activeTab === 'preview' ? (
                  <div className="flex flex-col h-full">
                    {/* Image Controls */}
                    <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-surface-900 border-b border-surface-200 dark:border-surface-800 text-xs text-surface-600 dark:text-surface-400">
                      <span className="font-mono">{imgZoom}% Zoom</span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setImgZoom((z) => Math.max(25, z - 25))}
                          className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-800"
                          title="Zoom out"
                        >
                          <ZoomOut className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => setImgZoom(100)}
                          className="px-2 py-0.5 rounded text-[11px] hover:bg-surface-100 dark:hover:bg-surface-800 font-mono"
                          title="Reset to 100%"
                        >
                          100%
                        </button>
                        <button
                          onClick={() => setImgZoom((z) => Math.min(300, z + 25))}
                          className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-800"
                          title="Zoom in"
                        >
                          <ZoomIn className="h-4 w-4" />
                        </button>
                      </div>
                    </div>

                    {/* Image Canvas */}
                    <div className="flex-1 overflow-auto flex items-center justify-center p-6 bg-surface-950/90 checkerboard-bg">
                      <img
                        src={mediaUrl}
                        alt={filename}
                        style={{ transform: `scale(${imgZoom / 100})`, transformOrigin: 'center center' }}
                        className="max-h-full max-w-full object-contain rounded-lg shadow-2xl transition-transform duration-150"
                      />
                    </div>
                  </div>
                ) : (
                  /* Image AI Caption & OCR Text Tab */
                  <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-white dark:bg-surface-900">
                    {docContent?.caption && (
                      <div className="rounded-2xl border border-sky-100 dark:border-sky-950 bg-sky-50/50 dark:bg-sky-950/20 p-5 space-y-2">
                        <div className="flex items-center gap-2 text-xs font-semibold text-sky-700 dark:text-sky-300 uppercase tracking-wider">
                          <Sparkles className="h-4 w-4" /> AI Scene Description (Multimodal Vision)
                        </div>
                        <p className="text-sm text-surface-800 dark:text-surface-200 leading-relaxed font-sans">
                          {docContent.caption}
                        </p>
                      </div>
                    )}

                    <div className="rounded-2xl border border-surface-200 dark:border-surface-800 bg-surface-50/50 dark:bg-surface-850 p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-surface-600 dark:text-surface-300 uppercase tracking-wider">
                          OCR Extracted Text & Layout
                        </span>
                        <button
                          onClick={() => copyText(docContent?.ocr_text || docContent?.content || '')}
                          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium border border-surface-200 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800"
                        >
                          {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                          {copied ? 'Copied' : 'Copy OCR Text'}
                        </button>
                      </div>
                      <div className="font-sans text-sm leading-relaxed text-surface-800 dark:text-surface-200 whitespace-pre-wrap break-words bg-white dark:bg-surface-900 p-4 rounded-xl border border-surface-200 dark:border-surface-800">
                        {docContent?.ocr_text || docContent?.content || 'No OCR text detected.'}
                      </div>
                    </div>
                  </div>
                )
              )}

              {/* 3. AUDIO RECORDING PREVIEW & PLAYER */}
              {isAudio && (
                <div className="flex-1 flex flex-col h-full bg-white dark:bg-surface-900 overflow-hidden">
                  {/* Hidden HTML5 Audio Element */}
                  <audio
                    ref={audioRef}
                    src={mediaUrl}
                    preload="metadata"
                  />

                  {/* Top Interactive Audio Player Card */}
                  <div className="p-6 sm:p-8 bg-gradient-to-b from-purple-50/50 to-transparent dark:from-purple-950/20 dark:to-transparent border-b border-surface-200 dark:border-surface-800 flex flex-col items-center justify-center gap-6">
                    {/* Animated Visualizer Bars */}
                    <div className="flex items-center justify-center gap-1 h-12 w-full max-w-md">
                      {[12, 28, 45, 20, 60, 85, 34, 70, 95, 50, 80, 40, 65, 30, 55, 90, 48, 72, 35, 60, 25, 40, 18, 30].map((h, i) => (
                        <div
                          key={i}
                          style={{
                            height: isPlaying ? `${Math.max(15, (h * (0.4 + 0.6 * Math.sin((currentTime * 4) + i))))}%` : '20%',
                          }}
                          className={`w-1.5 rounded-full transition-all duration-100 ${
                            isPlaying ? 'bg-purple-600 dark:bg-purple-400' : 'bg-surface-300 dark:bg-surface-700'
                          }`}
                        />
                      ))}
                    </div>

                    {/* Timeline Seek Bar */}
                    <div className="w-full max-w-xl space-y-1.5">
                      <div className="relative flex items-center">
                        <input
                          type="range"
                          min={0}
                          max={duration || 100}
                          step={0.1}
                          value={currentTime}
                          onChange={(e) => handleSeek(parseFloat(e.target.value))}
                          className="w-full h-2 rounded-lg bg-surface-200 dark:bg-surface-700 accent-purple-600 dark:accent-purple-400 cursor-pointer"
                        />
                      </div>
                      <div className="flex justify-between text-xs font-mono text-surface-500">
                        <span>{formatTime(currentTime)}</span>
                        <span>{formatTime(duration)}</span>
                      </div>
                    </div>

                    {/* Main Controls Row */}
                    <div className="flex items-center gap-4 sm:gap-6">
                      {/* Skip -10s */}
                      <button
                        onClick={() => handleSkip(-10)}
                        className="p-2.5 rounded-full text-surface-600 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 transition"
                        title="Rewind 10 seconds"
                      >
                        <Rewind className="h-5 w-5" />
                      </button>

                      {/* Play / Pause Primary Button */}
                      <button
                        onClick={togglePlay}
                        className="h-14 w-14 rounded-full bg-purple-600 text-white flex items-center justify-center shadow-lg shadow-purple-600/30 hover:bg-purple-700 active:scale-95 transition cursor-pointer"
                        title={isPlaying ? 'Pause' : 'Play'}
                      >
                        {isPlaying ? <Pause className="h-6 w-6" /> : <Play className="h-6 w-6 ml-0.5" />}
                      </button>

                      {/* Skip +10s */}
                      <button
                        onClick={() => handleSkip(10)}
                        className="p-2.5 rounded-full text-surface-600 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 transition"
                        title="Fast-forward 10 seconds"
                      >
                        <FastForward className="h-5 w-5" />
                      </button>

                      {/* Speed Selector */}
                      <div className="flex items-center border border-surface-200 dark:border-surface-700 rounded-lg overflow-hidden text-xs">
                        {[0.75, 1.0, 1.25, 1.5, 2.0].map((rate) => (
                          <button
                            key={rate}
                            onClick={() => handleSpeedChange(rate)}
                            className={`px-2 py-1 font-mono transition ${
                              playbackRate === rate
                                ? 'bg-purple-600 text-white font-semibold'
                                : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800'
                            }`}
                          >
                            {rate}x
                          </button>
                        ))}
                      </div>

                      {/* Volume / Mute */}
                      <div className="hidden sm:flex items-center gap-2">
                        <button
                          onClick={toggleMute}
                          className="p-2 rounded-lg text-surface-600 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 transition"
                          title={isMuted ? 'Unmute' : 'Mute'}
                        >
                          {isMuted || volume === 0 ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                        </button>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={isMuted ? 0 : volume}
                          onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                          className="w-16 h-1.5 rounded-lg bg-surface-200 dark:bg-surface-700 accent-purple-600 cursor-pointer"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Bottom Speech Transcript Panel */}
                  <div className="flex-1 flex flex-col overflow-hidden p-6 space-y-3">
                    <div className="flex items-center justify-between pb-2 border-b border-surface-200 dark:border-surface-800">
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-purple-500" />
                        <h4 className="font-semibold text-xs text-surface-700 dark:text-surface-300 uppercase tracking-wider">
                          Speech Transcript (Whisper ASR)
                        </h4>
                      </div>
                      <button
                        onClick={() => copyText(docContent?.content || '')}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium border border-surface-200 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800"
                      >
                        {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                        {copied ? 'Copied' : 'Copy Transcript'}
                      </button>
                    </div>

                    <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                      {docContent?.pages && docContent.pages.length > 0 ? (
                        docContent.pages.map((seg, idx) => {
                          const segStart = (seg as any).start ?? null
                          const isCurrent = segStart !== null && currentTime >= segStart && (idx === docContent.pages!.length - 1 || currentTime < ((docContent.pages![idx + 1] as any).start || 9999))
                          return (
                            <div
                              key={idx}
                              onClick={() => {
                                if (segStart !== null) handleSeek(segStart)
                              }}
                              className={`p-3 rounded-xl border transition-all cursor-pointer ${
                                isCurrent
                                  ? 'bg-purple-50 border-purple-300 text-purple-950 dark:bg-purple-950/40 dark:border-purple-800 dark:text-purple-200 shadow-xs ring-1 ring-purple-400'
                                  : 'bg-white border-surface-200 hover:bg-surface-50 dark:bg-surface-850 dark:border-surface-800 dark:hover:bg-surface-800 text-surface-800 dark:text-surface-200'
                              }`}
                            >
                              <div className="flex items-center gap-2 mb-1">
                                {segStart !== null && (
                                  <span className="font-mono text-[11px] font-semibold text-purple-600 dark:text-purple-400">
                                    [{formatTime(segStart)}]
                                  </span>
                                )}
                              </div>
                              <p className="text-sm font-sans leading-relaxed">{seg.text}</p>
                            </div>
                          )
                        })
                      ) : (
                        <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-850 text-surface-700 dark:text-surface-300 text-sm leading-relaxed whitespace-pre-wrap">
                          {docContent?.content || 'No transcript available for this audio file.'}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* 4. SPREADSHEET PREVIEW */}
              {isSheet && (
                <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-surface-900">
                  {/* Sheet Tabs */}
                  {docContent?.sheets && docContent.sheets.length > 1 && (
                    <div className="flex items-center gap-1 p-2 bg-surface-50 dark:bg-surface-850 border-b border-surface-200 dark:border-surface-800 overflow-x-auto">
                      {docContent.sheets.map((s, idx) => (
                        <button
                          key={s.title || idx}
                          onClick={() => setActiveSheetIdx(idx)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition ${
                            activeSheetIdx === idx
                              ? 'bg-emerald-600 text-white shadow-xs'
                              : 'text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-800'
                          }`}
                        >
                          {s.title || `Sheet ${idx + 1}`} ({s.rows.length} rows)
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Spreadsheet Grid */}
                  <div className="flex-1 overflow-auto p-4">
                    {(() => {
                      const curSheet = docContent?.sheets?.[activeSheetIdx] || { rows: [] }
                      const rows = curSheet.rows || []
                      if (rows.length === 0) {
                        return (
                          <div className="p-8 text-center text-xs text-surface-400">
                            Empty spreadsheet or no readable tabular data.
                          </div>
                        )
                      }
                      return (
                        <table className="w-full border-collapse text-xs">
                          <thead>
                            <tr className="bg-surface-100 dark:bg-surface-800 sticky top-0 z-10 shadow-xs">
                              <th className="p-2 border border-surface-200 dark:border-surface-700 font-mono text-[10px] text-surface-400 w-12 text-center">
                                #
                              </th>
                              {rows[0]?.map((col, cIdx) => (
                                <th
                                  key={cIdx}
                                  className="p-2 border border-surface-200 dark:border-surface-700 text-left font-semibold text-surface-900 dark:text-surface-100"
                                >
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {rows.slice(1).map((row, rIdx) => (
                              <tr
                                key={rIdx}
                                className="hover:bg-surface-50 dark:hover:bg-surface-850/50 transition-colors"
                              >
                                <td className="p-2 border border-surface-200 dark:border-surface-800 font-mono text-[10px] text-surface-400 text-center bg-surface-50 dark:bg-surface-850">
                                  {rIdx + 2}
                                </td>
                                {row.map((cell, cIdx) => (
                                  <td
                                    key={cIdx}
                                    className="p-2 border border-surface-200 dark:border-surface-800 text-surface-800 dark:text-surface-200 font-sans"
                                  >
                                    {cell}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )
                    })()}
                  </div>
                </div>
              )}

              {/* 5. CODE / TEXT / OTHER DOCUMENTS */}
              {!isPdf && !isImage && !isAudio && !isSheet && (
                <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-surface-900">
                  <div className="flex items-center justify-between p-3 border-b border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850">
                    <span className="text-xs font-mono text-surface-500 uppercase">
                      {isCode ? 'Source Code Document' : 'Document Content'}
                    </span>
                    <button
                      onClick={() => copyText(docContent?.content || '')}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium border border-surface-200 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800"
                    >
                      {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                      {copied ? 'Copied' : 'Copy All'}
                    </button>
                  </div>

                  <div className="flex-1 overflow-y-auto p-6">
                    {isCode ? (
                      <pre className="font-mono text-xs leading-relaxed text-surface-900 dark:text-surface-100 bg-surface-50 dark:bg-surface-950 p-4 rounded-xl border border-surface-200 dark:border-surface-800 overflow-x-auto">
                        <code>{docContent?.content || 'Empty file.'}</code>
                      </pre>
                    ) : (
                      <div className="font-sans text-sm leading-relaxed text-surface-800 dark:text-surface-200 whitespace-pre-wrap">
                        {docContent?.content || 'No text content available.'}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
