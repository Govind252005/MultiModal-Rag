import React, { useState, useEffect, useRef, useMemo } from 'react'
import {
  FileText,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2,
  X,
  Search,
  Loader2,
  AlertCircle,
  FileSpreadsheet,
  Presentation,
  CheckCircle2,
  Sparkles,
  Music,
} from 'lucide-react'
import type { Citation, DocumentContentResponse } from '../types'
import { getDocumentContent, getToken } from '../api'

export interface DocumentViewerProps {
  sessionId: string
  activeDocument: string
  activeCitation: Citation | null
  allCitations: Citation[]
  onSelectCitation: (cit: Citation) => void
  onClose: () => void
  isSplitView?: boolean
  onToggleSplit?: () => void
  activeQuery?: string
  activeAnswer?: string
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function normalizeChars(s: string): string {
  return s
    .replace(/[\u2010\u2011\u2012\u2013\u2014]/g, '-')
    .replace(/[\u00A0\u2002\u2003\u2009\u202F]/g, ' ')
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
}

function locatePhraseInText(pageText: string, targetPhrase: string): { start: number; end: number } | null {
  const clean = targetPhrase.trim()
  if (!clean || clean.length < 3) return null

  // 1. Direct substring match
  const exactIdx = pageText.indexOf(clean)
  if (exactIdx >= 0) {
    return { start: exactIdx, end: exactIdx + clean.length }
  }

  // 2. Case-insensitive exact match
  const lowerIdx = pageText.toLowerCase().indexOf(clean.toLowerCase())
  if (lowerIdx >= 0) {
    return { start: lowerIdx, end: lowerIdx + clean.length }
  }

  // 3. Normalized punctuation match (e.g. non-breaking hyphens \u2011, en-dash \u2013, unicode spaces)
  const normPage = normalizeChars(pageText)
  const normClean = normalizeChars(clean)
  const normExact = normPage.toLowerCase().indexOf(normClean.toLowerCase())
  if (normExact >= 0) {
    return { start: normExact, end: normExact + clean.length }
  }

  // 4. Multi-word regex match across newlines/whitespace with strict token boundaries
  const words = normClean.split(/\s+/).filter(Boolean)
  if (words.length === 0) return null

  const wordLengths = [
    words.length,
    Math.min(words.length, 12),
    Math.min(words.length, 8),
    Math.min(words.length, 5),
    Math.min(words.length, 3),
  ]

  for (const len of wordLengths) {
    if (len < 2 && words.length > 1) continue
    const subWords = words.slice(0, len)
    const pattern = subWords.map((w) => escapeRegex(w).replace(/-/g, '[-—–‑]')).join('\\s+')
    try {
      // Require word boundaries or whitespace so we never cut words (e.g. 'in' into 'i')
      const rx = new RegExp(`(?:^|\\s|\\b)(${pattern})(?:\\b|\\s|$)`, 'iu')
      const match = rx.exec(pageText)
      if (match && match[1]) {
        const offset = match.index + match[0].indexOf(match[1])
        return { start: offset, end: offset + match[1].length }
      }
    } catch {
      // ignore regex syntax issues
    }
  }

  return null
}

function snapToWordBoundary(s: string, maxLen: number): string {
  if (s.length <= maxLen) return s.trim()
  const cut = s.slice(0, maxLen)
  const lastSpace = Math.max(cut.lastIndexOf(' '), cut.lastIndexOf('\n'), cut.lastIndexOf('\t'))
  return (lastSpace > 15 ? cut.slice(0, lastSpace) : cut).trim()
}

function getCandidatePhrases(
  cit: Citation,
  activeQuery?: string,
  activeAnswer?: string,
  pageText?: string,
): string[] {
  const fullText = (cit.text || cit.snippet || '').trim()
  const candidatePool = [pageText || '', fullText].filter(Boolean)
  const candidates: string[] = []

  // 0. If activeAnswer is present, prioritize the exact answer text or key answer phrases
  if (activeAnswer) {
    const cleanAnswer = activeAnswer
      .replace(/(?:\[|【|［)\s*\d+\s*(?:\]|】|］)/g, '')
      .replace(/^\[LLM unavailable[^\]]*\]/i, '')
      .trim()

    if (cleanAnswer && cleanAnswer.length >= 3) {
      if (!candidates.includes(cleanAnswer)) candidates.push(cleanAnswer)
      const ansLines = cleanAnswer
        .split(/(?:\r?\n+|(?<=[.!?])\s+)/)
        .map((s) => s.trim())
        .filter((s) => s.length >= 4)
      for (const line of ansLines) {
        if (!candidates.includes(line)) candidates.push(line)
      }
    }
  }

  // 1. If user asked "who submitted" or author/supervisor query, prioritize exact submitter block from page
  if (activeQuery && /\b(who|author|submit|submitted|prepared|student|supervisor)\b/i.test(activeQuery)) {
    for (const src of candidatePool) {
      const authorMatch = src.match(/(?:submitted\s+by|author|prepared\s+by)[:\s]*\n*([^\r\n]+)/i)
      if (authorMatch && authorMatch[1]) {
        const name = authorMatch[1].trim()
        if (name.length >= 3 && !candidates.includes(name)) {
          candidates.push(name)
        }
        const fullBlock = authorMatch[0].trim()
        if (!candidates.includes(fullBlock)) {
          candidates.push(fullBlock)
        }
      }
    }
  }

  // 2. Multi-line entity patterns (e.g. "Submitted by\nGOVIND SHREELOCHAN", "Aim\nTo specify...")
  for (const src of candidatePool) {
    const submittedMulti = src.match(/submitted\s+by[:\s]*\n*([^\r\n]+)/i)
    if (submittedMulti && submittedMulti[1]) {
      const authorName = submittedMulti[1].trim()
      if (authorName.length >= 3 && !candidates.includes(authorName)) {
        candidates.push(authorName)
      }
      const fullSubmittedBlock = submittedMulti[0].trim()
      if (!candidates.includes(fullSubmittedBlock)) {
        candidates.push(fullSubmittedBlock)
      }
    }

    const aimMulti = src.match(/\baim[:\s]*\n*([^\r\n]+)/i)
    if (aimMulti && aimMulti[1]) {
      const aimText = aimMulti[1].trim()
      if (aimText.length >= 6 && !candidates.includes(aimText)) {
        candidates.push(aimText)
      }
    }
  }

  if (!fullText) return candidates

  // 3. Segment analysis from citation text
  const rawSegments = fullText
    .split(/(?:\r?\n+|(?<=[.!?])\s+)/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 6)

  // Prioritize segments matching user query or key entity phrases
  if (activeQuery) {
    const qWords = activeQuery.toLowerCase().split(/\W+/).filter((w) => w.length > 2)
    const scored = rawSegments.map((seg) => {
      const segLower = seg.toLowerCase()
      let score = 0
      for (const w of qWords) {
        if (segLower.includes(w)) score += 3
      }
      if (/submitted\s+by|author|supervisor|prepared\s+by|aim|theory|total|section|liability|rule/i.test(seg)) {
        score += 5
      }
      return { seg, score }
    })
    scored.sort((a, b) => b.score - a.score)
    for (const item of scored) {
      if (item.score > 0 && !candidates.includes(item.seg)) candidates.push(item.seg)
    }
  }

  // Also prioritize lines with salient entity prefixes
  for (const seg of rawSegments) {
    if (/submitted\s+by|author|supervisor|aim|theory|section|rule|article|fact/i.test(seg)) {
      if (!candidates.includes(seg)) candidates.push(seg)
    }
  }

  // Append remaining segments in natural order
  for (const seg of rawSegments) {
    if (!candidates.includes(seg)) candidates.push(seg)
  }

  if (!candidates.includes(fullText)) {
    candidates.push(snapToWordBoundary(fullText, 120))
  }

  return candidates
}

export default function DocumentViewer({
  sessionId,
  activeDocument,
  activeCitation,
  allCitations,
  onSelectCitation,
  onClose,
  isSplitView = false,
  activeQuery,
  activeAnswer,
}: DocumentViewerProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [docContent, setDocContent] = useState<DocumentContentResponse | null>(null)
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [activeSheetIndex, setActiveSheetIndex] = useState<number>(0)
  const [zoomLevel, setZoomLevel] = useState<number>(100)
  const [viewMode, setViewMode] = useState<'interactive' | 'binary'>('interactive')
  const [searchQuery, setSearchQuery] = useState('')
  const [fullWidth, setFullWidth] = useState(false)
  const [mobileTab, setMobileTab] = useState<'document' | 'annotations'>('document')
  const [showAnnotations, setShowAnnotations] = useState(true)

  const isSplitPane = isSplitView && !fullWidth

  const textContainerRef = useRef<HTMLDivElement>(null)
  const activeHighlightRef = useRef<HTMLElement | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    if (activeCitation && (activeCitation.modality === 'audio' || docContent?.modality === 'audio')) {
      const startSec = Number(activeCitation.start || activeCitation.timestamp || 0)
      if (audioRef.current && !isNaN(startSec) && startSec > 0) {
        audioRef.current.currentTime = startSec
        audioRef.current.play().catch(() => {/* browser auto-play policy catch */})
      }
    }
  }, [activeCitation, docContent])

  const effectiveSessionId = sessionId || activeCitation?.session_id || ''

  // 1. Fetch document content when activeDocument or sessionId changes
  useEffect(() => {
    let canceled = false
    if (!activeDocument || !effectiveSessionId) return

    setLoading(true)
    setError(null)

    getDocumentContent(effectiveSessionId, activeDocument)
      .then((data) => {
        if (canceled) return
        setDocContent(data)
        setLoading(false)

        // If activeCitation has a valid page, set current page
        if (activeCitation?.file === activeDocument && activeCitation.page != null && activeCitation.page > 0) {
          setCurrentPage(activeCitation.page)
        } else {
          setCurrentPage(1)
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
  }, [sessionId, activeDocument])

  // 2. Synchronize current page when user selects a different citation
  useEffect(() => {
    if (activeCitation && activeCitation.file === activeDocument) {
      if (activeCitation.page != null && activeCitation.page > 0) {
        setCurrentPage(activeCitation.page)
      }
    }
  }, [activeCitation, activeDocument])

  // 3. Scroll active highlight into view
  useEffect(() => {
    if (activeHighlightRef.current) {
      activeHighlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [currentPage, activeCitation, docContent])

  // Citations for the current document
  const docCitations = useMemo(() => {
    return allCitations.filter((c) => c.file === activeDocument)
  }, [allCitations, activeDocument])

  // Filtered citations in sidebar (displays all answer citations to enable seamless cross-document navigation)
  const filteredCitations = useMemo(() => {
    if (!searchQuery.trim()) return allCitations
    const q = searchQuery.toLowerCase()
    return allCitations.filter(
      (c) =>
        c.file.toLowerCase().includes(q) ||
        c.snippet.toLowerCase().includes(q) ||
        (c.text && c.text.toLowerCase().includes(q)) ||
        (c.page != null && `page ${c.page}`.includes(q))
    )
  }, [allCitations, searchQuery])

  // Total pages calculation
  const totalPages = useMemo(() => {
    if (!docContent) return 1
    if (docContent.page_count && docContent.page_count > 0) return docContent.page_count
    if (docContent.pages && docContent.pages.length > 0) return docContent.pages.length
    if (docContent.sheets && docContent.sheets.length > 0) return docContent.sheets.length
    return 1
  }, [docContent])

  // Page navigation helpers
  function goToPrevPage() {
    setCurrentPage((p) => Math.max(1, p - 1))
  }
  function goToNextPage() {
    setCurrentPage((p) => Math.min(totalPages, p + 1))
  }

  // Zoom controls
  function handleZoomIn() {
    setZoomLevel((z) => Math.min(200, z + 15))
  }
  function handleZoomOut() {
    setZoomLevel((z) => Math.max(70, z - 15))
  }
  function handleResetZoom() {
    setZoomLevel(100)
  }

  // Active page text
  const currentPageText = useMemo(() => {
    if (!docContent) return ''
    if (docContent.pages && docContent.pages.length > 0) {
      const p = docContent.pages.find((page) => page.page_number === currentPage)
      return p ? p.text : docContent.pages[0]?.text || ''
    }
    if (docContent.content) return docContent.content
    return ''
  }, [docContent, currentPage])

  // Text matching & Highlighting Engine (Unicode, Devanagari, and whitespace aware)
  const renderedTextWithHighlights = useMemo(() => {
    if (!currentPageText) return null

    // Find all citations on this page or without page restrictions
    const citationsOnThisPage = docCitations.filter(
      (c) => c.page === null || c.page === currentPage || (!docContent?.has_pages)
    )

    if (citationsOnThisPage.length === 0) {
      return <div className="whitespace-pre-wrap leading-relaxed text-surface-800 dark:text-surface-200">{currentPageText}</div>
    }

    // Attempt to locate passages in page text
    interface MatchRange {
      start: number
      end: number
      citation: Citation
      isActive: boolean
    }

    const matches: MatchRange[] = []

    for (const cit of citationsOnThisPage) {
      const phrases = getCandidatePhrases(cit, activeQuery, activeAnswer, currentPageText)
      let matchFound = false

      for (const phrase of phrases) {
        const loc = locatePhraseInText(currentPageText, phrase)
        if (loc && loc.end > loc.start) {
          matches.push({
            start: loc.start,
            end: loc.end,
            citation: cit,
            isActive: activeCitation?.index === cit.index,
          })
          matchFound = true
          break
        }
      }

      // Fallback: try first 60 characters of citation text or snippet
      if (!matchFound) {
        const rawTarget = (cit.text || cit.snippet || '').trim().replace(/\s+/g, ' ')
        const probe = rawTarget.slice(0, 60)
        const loc = locatePhraseInText(currentPageText, probe)
        if (loc && loc.end > loc.start) {
          matches.push({
            start: loc.start,
            end: loc.end,
            citation: cit,
            isActive: activeCitation?.index === cit.index,
          })
        }
      }
    }

    // If no match located, return plain text
    if (matches.length === 0) {
      return (
        <div className="whitespace-pre-wrap leading-relaxed text-surface-800 dark:text-surface-200 break-words font-sans">
          {currentPageText}
        </div>
      )
    }

    // Sort matches by start position
    matches.sort((a, b) => a.start - b.start)

    // Build segments
    const elements: React.ReactNode[] = []
    let lastIdx = 0

    matches.forEach((m, i) => {
      if (m.start > lastIdx) {
        elements.push(
          <span key={`text-${lastIdx}-${m.start}`}>
            {currentPageText.slice(lastIdx, m.start)}
          </span>
        )
      }

      const highlightedSlice = currentPageText.slice(m.start, m.end)
      const isAct = m.isActive

      elements.push(
        <mark
          key={`mark-${i}-${m.start}`}
          ref={isAct ? (el) => { activeHighlightRef.current = el } : undefined}
          onClick={() => onSelectCitation(m.citation)}
          className={`cursor-pointer rounded px-1 py-0.5 transition-all font-medium ${
            isAct
              ? 'bg-amber-300 text-amber-950 dark:bg-amber-400 dark:text-amber-950 ring-2 ring-amber-500 shadow-sm'
              : 'bg-emerald-100 text-emerald-950 dark:bg-emerald-900/50 dark:text-emerald-200 hover:bg-emerald-200'
          }`}
          title={`Citation [${m.citation.index}] - ${m.citation.file}${m.citation.page ? `, p. ${m.citation.page}` : ''}`}
        >
          {highlightedSlice}
          <span className="ml-1 inline-flex items-center justify-center rounded bg-surface-900/10 px-1 py-0.2 text-[10px] font-mono font-bold align-super">
            [{m.citation.index}]
          </span>
        </mark>
      )

      lastIdx = m.end
    })

    if (lastIdx < currentPageText.length) {
      elements.push(
        <span key={`text-end-${lastIdx}`}>
          {currentPageText.slice(lastIdx)}
        </span>
      )
    }

    return (
      <div className="whitespace-pre-wrap leading-relaxed text-surface-800 dark:text-surface-200 break-words font-sans">
        {elements}
      </div>
    )
  }, [currentPageText, docCitations, activeCitation, currentPage, docContent, activeQuery, activeAnswer])

  // Check if active citation has an exact verified match on current page
  const hasVerifiedMatchOnPage = useMemo(() => {
    if (!activeCitation || !currentPageText) return false
    const phrases = getCandidatePhrases(activeCitation, activeQuery, activeAnswer, currentPageText)
    for (const p of phrases) {
      if (locatePhraseInText(currentPageText, p)) return true
    }
    const probe = (activeCitation.text || activeCitation.snippet || '').trim().slice(0, 60)
    return !!locatePhraseInText(currentPageText, probe)
  }, [activeCitation, currentPageText, activeQuery, activeAnswer])

  return (
    <div
      className={`flex flex-col h-full bg-white dark:bg-surface-900 border-l border-surface-200 dark:border-surface-800 transition-all duration-200 ${
        fullWidth ? 'fixed inset-0 z-50' : 'w-full'
      }`}
      data-testid="evidence-document-viewer"
    >
      {/* 1. Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850 px-4 py-2.5">
        <div className="flex items-center gap-2.5 min-w-0">
          {docContent?.modality === 'pdf' ? (
            <FileText className="h-5 w-5 text-rose-500 shrink-0" />
          ) : docContent?.modality === 'xlsx' ? (
            <FileSpreadsheet className="h-5 w-5 text-emerald-600 shrink-0" />
          ) : docContent?.modality === 'pptx' ? (
            <Presentation className="h-5 w-5 text-amber-500 shrink-0" />
          ) : (
            <FileText className="h-5 w-5 text-brand-600 shrink-0" />
          )}

          <div className="min-w-0">
            <h3 className="truncate font-semibold text-sm text-surface-900 dark:text-surface-100" title={activeDocument}>
              {activeDocument}
            </h3>
            <div className="flex items-center gap-2 text-[11px] text-surface-500 dark:text-surface-400">
              <span className="uppercase font-mono font-medium">{docContent?.modality || 'DOC'}</span>
              <span>&middot;</span>
              {docContent?.has_pages ? (
                <span className="font-medium text-brand-600 dark:text-brand-400">
                  Page {currentPage} of {totalPages}
                </span>
              ) : (
                <span className="text-amber-600 dark:text-amber-400">Text-level evidence</span>
              )}
            </div>
          </div>
        </div>

        {/* Toolbar Controls */}
        <div className="flex items-center gap-1.5">
          {/* Page Pagination (when format has pages) */}
          {docContent?.has_pages && (
            <div className="flex items-center rounded-lg border border-surface-200 bg-white dark:border-surface-700 dark:bg-surface-800 px-1 py-0.5">
              <button
                type="button"
                onClick={goToPrevPage}
                disabled={currentPage <= 1}
                className="p-1 rounded text-surface-600 hover:bg-surface-100 disabled:opacity-30 dark:text-surface-300 dark:hover:bg-surface-700"
                title="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-2 text-xs font-mono font-medium text-surface-700 dark:text-surface-300">
                {currentPage} / {totalPages}
              </span>
              <button
                type="button"
                onClick={goToNextPage}
                disabled={currentPage >= totalPages}
                className="p-1 rounded text-surface-600 hover:bg-surface-100 disabled:opacity-30 dark:text-surface-300 dark:hover:bg-surface-700"
                title="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Zoom Controls */}
          <div className="hidden sm:flex items-center rounded-lg border border-surface-200 bg-white dark:border-surface-700 dark:bg-surface-800 px-1 py-0.5">
            <button
              type="button"
              onClick={handleZoomOut}
              className="p-1 rounded text-surface-600 hover:bg-surface-100 dark:text-surface-300 dark:hover:bg-surface-700"
              title="Zoom out"
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={handleResetZoom}
              className="px-1.5 text-xs font-mono text-surface-700 dark:text-surface-300 hover:underline"
              title="Reset to 100%"
            >
              {zoomLevel}%
            </button>
            <button
              type="button"
              onClick={handleZoomIn}
              className="p-1 rounded text-surface-600 hover:bg-surface-100 dark:text-surface-300 dark:hover:bg-surface-700"
              title="Zoom in"
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* PDF View Mode Switcher (Interactive vs Binary) */}
          {docContent?.modality === 'pdf' && (
            <div className="flex items-center rounded-lg border border-surface-200 bg-white dark:border-surface-700 dark:bg-surface-800 p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setViewMode('interactive')}
                className={`px-2 py-1 rounded font-medium transition ${
                  viewMode === 'interactive'
                    ? 'bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300'
                    : 'text-surface-600 hover:text-surface-900 dark:text-surface-400'
                }`}
                title="Interactive Evidence Text View with verified highlights"
              >
                Evidence
              </button>
              <button
                type="button"
                onClick={() => setViewMode('binary')}
                className={`px-2 py-1 rounded font-medium transition ${
                  viewMode === 'binary'
                    ? 'bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300'
                    : 'text-surface-600 hover:text-surface-900 dark:text-surface-400'
                }`}
                title="Embedded PDF document page view"
              >
                PDF View
              </button>
            </div>
          )}

          {/* Full Width Toggle */}
          <button
            type="button"
            onClick={() => setFullWidth(!fullWidth)}
            className="p-1.5 rounded-lg text-surface-500 hover:bg-surface-100 dark:text-surface-400 dark:hover:bg-surface-800"
            title={fullWidth ? 'Restore split view' : 'Maximize viewer'}
          >
            {fullWidth ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </button>

          {/* Annotations Toggle Button */}
          <button
            type="button"
            data-testid="toggle-annotations-btn"
            onClick={() => {
              if (isSplitPane || !fullWidth) {
                setMobileTab((curr) => (curr === 'annotations' ? 'document' : 'annotations'))
              } else {
                setShowAnnotations(!showAnnotations)
              }
            }}
            className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition border ${
              (isSplitPane || !fullWidth ? mobileTab === 'annotations' : showAnnotations)
                ? 'bg-brand-50 border-brand-300 text-brand-700 dark:bg-brand-950 dark:border-brand-800 dark:text-brand-300'
                : 'bg-white border-surface-200 text-surface-600 hover:bg-surface-50 dark:bg-surface-800 dark:border-surface-700 dark:text-surface-300'
            }`}
            title="Toggle Annotations sidebar"
          >
            <span>Annotations</span>
            <span className="rounded-full bg-brand-100 dark:bg-brand-900 px-1.5 py-0.2 text-[10px] font-mono font-bold text-brand-700 dark:text-brand-300">
              {docCitations.length}
            </span>
          </button>

          {/* Close Button */}
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-surface-500 hover:bg-rose-50 hover:text-rose-600 dark:text-surface-400 dark:hover:bg-rose-950 dark:hover:text-rose-300"
            title="Close viewer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Responsive Sub-Navigation Bar: Allows toggling between Document and Annotations without horizontal squeezing */}
      <div
        className={`flex items-center border-b border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850 p-2 gap-2 shrink-0 ${
          fullWidth ? 'lg:hidden' : 'flex'
        }`}
      >
        <button
          type="button"
          data-testid="mobile-tab-document"
          onClick={() => setMobileTab('document')}
          className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold text-center transition flex items-center justify-center gap-1.5 ${
            mobileTab === 'document'
              ? 'bg-white dark:bg-surface-800 text-brand-600 dark:text-brand-300 shadow-2xs border border-surface-200 dark:border-surface-700'
              : 'text-surface-600 dark:text-surface-400 hover:text-surface-900'
          }`}
        >
          <FileText className="h-3.5 w-3.5" />
          <span>Document View</span>
        </button>
        <button
          type="button"
          data-testid="mobile-tab-annotations"
          onClick={() => setMobileTab('annotations')}
          className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold text-center transition flex items-center justify-center gap-1.5 ${
            mobileTab === 'annotations'
              ? 'bg-white dark:bg-surface-800 text-brand-600 dark:text-brand-300 shadow-2xs border border-surface-200 dark:border-surface-700'
              : 'text-surface-600 dark:text-surface-400 hover:text-surface-900'
          }`}
        >
          <span>Annotations & Evidence</span>
          <span className="rounded-full bg-brand-100 dark:bg-brand-950 px-1.5 py-0.2 text-[10px] font-mono font-bold text-brand-700 dark:text-brand-300">
            {docCitations.length}
          </span>
        </button>
      </div>

      {/* 2. Main Dual-Pane Body: Document Viewer (Left) + Annotations Sidebar (Right) */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Document Display Area */}
        <div
          data-testid="document-content-surface"
          className={`flex-1 flex flex-col overflow-y-auto p-3 sm:p-6 bg-surface-100/60 dark:bg-surface-950 scroll-thin min-w-0 ${
            fullWidth
              ? 'flex w-full'
              : mobileTab === 'document'
              ? 'flex w-full'
              : 'hidden'
          }`}
        >
          {loading ? (
            <div className="flex flex-col items-center justify-center flex-1 py-16 text-surface-400">
              <Loader2 className="h-8 w-8 animate-spin text-brand-600 mb-3" />
              <p className="text-sm font-medium">Loading document and verifying citations...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center flex-1 py-16 text-center max-w-md mx-auto">
              <AlertCircle className="h-10 w-10 text-rose-500 mb-3" />
              <h4 className="text-sm font-semibold text-surface-900 dark:text-surface-100 mb-1">
                Unable to Open Document
              </h4>
              <p className="text-xs text-surface-500 dark:text-surface-400 mb-4">{error}</p>
            </div>
          ) : (
            <div className="mx-auto w-full max-w-4xl space-y-4" style={{ zoom: `${zoomLevel}%` }}>
              {/* Active Citation Badge Banner */}
              {activeCitation && (
                <div className="rounded-xl border border-brand-200 bg-brand-50/80 p-3 text-xs text-brand-900 dark:border-brand-900 dark:bg-brand-950/40 dark:text-brand-200 flex items-center justify-between shadow-2xs">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center justify-center rounded bg-brand-600 px-2 py-0.5 font-mono text-xs font-bold text-white">
                      [{activeCitation.index}]
                    </span>
                    <span className="font-semibold">Active Supporting Evidence</span>
                    {activeCitation.page != null && (
                      <span className="rounded bg-brand-100 px-1.5 py-0.5 font-mono text-[10px] text-brand-800 dark:bg-brand-900 dark:text-brand-300">
                        Page {activeCitation.page}
                      </span>
                    )}
                  </div>
                  {hasVerifiedMatchOnPage && (
                    <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Exact Match Highlighted
                    </span>
                  )}
                </div>
              )}

              {/* Verified Excerpt Fallback Card (when exact visual match cannot be located on the page) */}
              {activeCitation && !hasVerifiedMatchOnPage && (
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-surface-800 dark:bg-surface-900">
                  <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
                    <Sparkles className="h-4 w-4 text-amber-500" />
                    <span>Verified Source Passage (Visual location fallback)</span>
                  </div>
                  <p className="text-xs text-surface-500 dark:text-surface-400 mb-2">
                    Exact character position could not be automatically anchored in page layout text. Displaying the exact retrieved source chunk below without fabrication:
                  </p>
                  <blockquote className="rounded-lg bg-surface-50 p-3 text-xs italic text-surface-800 border-l-4 border-amber-500 dark:bg-surface-800 dark:text-surface-200 font-sans leading-relaxed whitespace-pre-wrap">
                    "{activeCitation.text || activeCitation.snippet}"
                  </blockquote>
                </div>
              )}

              {/* View Mode: Binary PDF iframe embed */}
              {viewMode === 'binary' && docContent?.raw_url ? (
                <div className="rounded-2xl border border-surface-200 bg-white shadow-sm overflow-hidden dark:border-surface-800 dark:bg-surface-900 h-[650px] flex flex-col">
                  <div className="flex items-center justify-between px-3 py-1.5 bg-surface-50 dark:bg-surface-850 border-b border-surface-200 dark:border-surface-800 text-xs text-surface-500">
                    <span>Native PDF Document Viewer (Page {currentPage})</span>
                    <a
                      href={`${docContent.raw_url}?token=${encodeURIComponent(getToken())}#page=${currentPage}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-brand-600 hover:text-brand-700 dark:text-brand-400 font-medium underline flex items-center gap-1"
                    >
                      Open PDF in new tab &rarr;
                    </a>
                  </div>
                  <object
                    key={`pdf-obj-${docContent?.filename || activeDocument}-p${currentPage}`}
                    data={`${docContent.raw_url}?token=${encodeURIComponent(getToken())}#page=${currentPage}`}
                    type="application/pdf"
                    className="w-full flex-1 border-0"
                    title={activeDocument}
                  >
                    <iframe
                      key={`pdf-iframe-${docContent?.filename || activeDocument}-p${currentPage}`}
                      src={`${docContent.raw_url}?token=${encodeURIComponent(getToken())}#page=${currentPage}`}
                      title={activeDocument}
                      className="w-full h-full border-0"
                    >
                      <div className="flex flex-col items-center justify-center h-full p-8 text-center bg-surface-50 dark:bg-surface-850">
                        <p className="text-sm text-surface-600 dark:text-surface-300 mb-3">
                          PDF inline preview blocked by browser policy.
                        </p>
                        <a
                          href={`${docContent.raw_url}?token=${encodeURIComponent(getToken())}#page=${currentPage}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-4 py-2 rounded-xl bg-brand-600 text-white text-xs font-semibold shadow hover:bg-brand-700 transition"
                        >
                          Open PDF in Dedicated Window &rarr;
                        </a>
                      </div>
                    </iframe>
                  </object>
                </div>
              ) : (docContent?.modality === 'audio' || activeCitation?.modality === 'audio') ? (
                /* Interactive Audio Player & Synchronized Speech Transcript */
                <div className="rounded-2xl border border-surface-200 bg-white p-6 sm:p-8 shadow-sm dark:border-surface-800 dark:bg-surface-900 flex flex-col gap-6">
                  <div className="flex items-center gap-3 pb-4 border-b border-surface-100 dark:border-surface-800">
                    <div className="h-10 w-10 rounded-xl bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0 shadow-2xs">
                      <Music className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-surface-900 dark:text-surface-100 text-sm">
                        Audio Recording &amp; Speech Evidence
                      </h3>
                      <p className="text-xs text-surface-500">
                        {activeCitation?.start !== undefined
                          ? `Active citation timestamp: ${Math.floor(Number(activeCitation.start) / 60)}:${String(Math.floor(Number(activeCitation.start) % 60)).padStart(2, '0')}`
                          : 'Interactive audio player with timestamp-synchronized seeking'}
                      </p>
                    </div>
                  </div>

                  {docContent?.raw_url && (
                    <div className="rounded-xl bg-surface-50 dark:bg-surface-850 p-4 border border-surface-200 dark:border-surface-800">
                      <audio
                        ref={audioRef}
                        controls
                        src={`${docContent.raw_url}?token=${encodeURIComponent(getToken())}`}
                        className="w-full"
                        aria-label="Audio evidence player"
                      />
                    </div>
                  )}

                  <div className="space-y-3">
                    <span className="text-xs font-semibold uppercase tracking-wider text-surface-500">
                      Speech Transcript Evidence
                    </span>
                    <div
                      ref={textContainerRef}
                      className="rounded-xl border border-surface-200 bg-surface-50/50 p-4 font-sans text-sm leading-relaxed whitespace-pre-wrap break-words dark:border-surface-800 dark:bg-surface-850/50"
                    >
                      {renderedTextWithHighlights}
                    </div>
                  </div>
                </div>
              ) : docContent?.modality === 'xlsx' && docContent.sheets ? (
                /* Spreadsheet Grid Viewer */
                <div className="rounded-2xl border border-surface-200 bg-white shadow-sm overflow-hidden dark:border-surface-800 dark:bg-surface-900">
                  {/* Sheet tabs */}
                  <div className="flex items-center gap-1 border-b border-surface-200 bg-surface-50 px-3 py-2 dark:border-surface-800 dark:bg-surface-850">
                    {docContent.sheets.map((sheet, sIdx) => (
                      <button
                        key={sheet.title}
                        type="button"
                        onClick={() => {
                          setActiveSheetIndex(sIdx)
                          setCurrentPage(sIdx + 1)
                        }}
                        className={`rounded-lg px-3 py-1 text-xs font-medium transition ${
                          activeSheetIndex === sIdx
                            ? 'bg-white text-emerald-700 shadow-2xs dark:bg-surface-800 dark:text-emerald-400'
                            : 'text-surface-600 hover:text-surface-900 dark:text-surface-400'
                        }`}
                      >
                        {sheet.title}
                      </button>
                    ))}
                  </div>

                  {/* Spreadsheet Table */}
                  <div className="overflow-x-auto p-4 max-h-[500px]">
                    {docContent.sheets[activeSheetIndex] ? (
                      <table className="w-full border-collapse text-xs">
                        <tbody>
                          {docContent.sheets[activeSheetIndex].rows.map((row, rIdx) => (
                            <tr key={rIdx} className="hover:bg-surface-50 dark:hover:bg-surface-800/50">
                              <td className="w-8 border border-surface-200 bg-surface-50 p-1.5 text-center font-mono text-[10px] text-surface-400 dark:border-surface-800 dark:bg-surface-850">
                                {rIdx + 1}
                              </td>
                              {row.map((cell, cIdx) => (
                                <td key={cIdx} className="border border-surface-200 p-2 text-surface-800 dark:border-surface-800 dark:text-surface-200">
                                  {cell}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <p className="text-xs text-surface-400 p-4">No sheet rows available.</p>
                    )}
                  </div>
                </div>
              ) : (
                /* Interactive Evidence Text Viewer with Highlights */
                <div
                  ref={textContainerRef}
                  className="rounded-2xl border border-surface-200 bg-white p-6 sm:p-8 shadow-sm dark:border-surface-800 dark:bg-surface-900 font-sans text-sm leading-relaxed whitespace-pre-wrap break-words"
                >
                  {renderedTextWithHighlights}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 3. Evidence & Annotations Sidebar */}
        <div
          data-testid="annotations-surface"
          className={`border-l border-surface-200 bg-white dark:border-surface-800 dark:bg-surface-900 flex flex-col shrink-0 min-w-0 ${
            fullWidth
              ? showAnnotations
                ? 'hidden lg:flex lg:w-72 2xl:w-80'
                : 'hidden'
              : mobileTab === 'annotations'
              ? 'flex w-full'
              : 'hidden'
          }`}
        >
          {/* Back-to-Document Quick Action */}
          <div className={`${fullWidth ? 'lg:hidden' : 'flex'} p-2.5 bg-brand-50/70 dark:bg-brand-950/40 border-b border-brand-100 dark:border-brand-900 items-center justify-between`}>
            <button
              type="button"
              data-testid="return-to-document-btn"
              onClick={() => setMobileTab('document')}
              className="flex items-center gap-1.5 text-xs font-semibold text-brand-700 dark:text-brand-300 hover:underline"
            >
              <ChevronLeft className="h-4 w-4" />
              <span>&larr; Return to Document View</span>
            </button>
            <span className="text-[11px] text-brand-600 dark:text-brand-400">
              Tap card to view page
            </span>
          </div>

          <div className="p-3 border-b border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850">
            <h4 className="font-semibold text-xs text-surface-700 dark:text-surface-200 uppercase tracking-wider mb-2">
              Annotations & Evidence ({docCitations.length})
            </h4>

            {/* Annotation search filter */}
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-surface-400" />
              <input
                type="text"
                placeholder="Search annotations by text..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-surface-200 bg-white pl-8 pr-3 py-1.5 text-xs text-surface-800 placeholder-surface-400 focus:border-brand-500 focus:outline-hidden dark:border-surface-700 dark:bg-surface-800 dark:text-surface-200"
              />
            </div>
          </div>

          {/* Annotations List */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5 scroll-thin">
            {filteredCitations.length === 0 ? (
              <div className="text-center py-8 text-surface-400 text-xs">
                No citations match the filter.
              </div>
            ) : (
              filteredCitations.map((c) => {
                const isSelected = activeCitation?.index === c.index
                return (
                  <div
                    key={`ann-${c.index}`}
                    data-testid={`annotation-card-${c.index}`}
                    onClick={() => {
                      onSelectCitation(c)
                      if (c.page != null && c.page > 0) {
                        setCurrentPage(c.page)
                      }
                      setMobileTab('document')
                    }}
                    className={`cursor-pointer rounded-xl border p-3 transition-all ${
                      isSelected
                        ? 'border-brand-500 bg-brand-50/70 dark:bg-brand-950/40 shadow-xs'
                        : 'border-surface-200 bg-white hover:border-surface-300 dark:border-surface-800 dark:bg-surface-850'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="inline-flex items-center justify-center rounded bg-brand-600 px-1.5 py-0.5 font-mono text-[10px] font-bold text-white shrink-0">
                          [{c.index}]
                        </span>
                        <span className="truncate text-[10px] font-medium text-surface-600 dark:text-surface-300" title={c.file}>
                          {c.file}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono text-surface-400 shrink-0">
                        {c.page != null ? `p. ${c.page}` : c.source_type}
                      </span>
                    </div>

                    <p className="line-clamp-3 text-xs italic text-surface-700 dark:text-surface-300 mb-2">
                      "{c.snippet}"
                    </p>

                    <div className="flex items-center justify-between text-[10px] text-surface-400 border-t border-surface-100 dark:border-surface-800 pt-1.5">
                      <span className="text-brand-600 dark:text-brand-400 font-medium">
                        Supporting evidence
                      </span>
                      <span>Jump to page &rarr;</span>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
