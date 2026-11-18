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
  Image as ImageIcon,
  Copy,
  ExternalLink,
} from 'lucide-react'
import type { Citation, DocumentContentResponse } from '../types'
import { getDocumentContent, getToken } from '../api'
import AuthImage from './AuthImage'

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
  onPopOutPreview?: (filename: string, sessionId?: string, page?: number) => void
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function normalizeChars(s: string): string {
  return s
    .replace(/[\u2010\u2011\u2012\u2013\u2014]/g, '-')
    .replace(/[\u00A0\u2002\u2003\u2009\u202F]/g, ' ')
    .replace(/[\u2018\u2019\u02BC`]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
}

function normalizeString(s: string): string {
  return (s || '')
    .toLowerCase()
    .replace(/[\u2010\u2011\u2012\u2013\u2014]/g, '-')
    .replace(/[\u00A0\u2002\u2003\u2009\u202F]/g, ' ')
    .replace(/[\u2018\u2019\u02BC`]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/\s+/g, ' ')
    .trim()
}

interface SpanOffset {
  start: number
  end: number
  text: string
  norm: string
  joinedStart: number
  joinedEnd: number
}

function findExactHighlightRange(
  pageText: string,
  targetEvidence: string,
  boldEntity?: string
): { start: number; end: number } | null {
  const normTarget = normalizeString(targetEvidence)
  if (!normTarget || normTarget.length < 5) return null

  // 1. Build contiguous span map from pageText
  const lineRegex = /[^\r\n]+(?:\r?\n|$)/g
  const spans: SpanOffset[] = []
  let m: RegExpExecArray | null
  let runningJoined = 0
  const joinedParts: string[] = []

  while ((m = lineRegex.exec(pageText)) !== null) {
    const rawLine = m[0]
    const start = m.index
    const trimmedLine = rawLine.replace(/[\r\n]+$/, '')
    if (trimmedLine.trim().length > 0) {
      const normLine = normalizeString(trimmedLine)
      const joinedStart = runningJoined
      const joinedEnd = joinedStart + normLine.length
      spans.push({
        start,
        end: start + trimmedLine.length,
        text: trimmedLine,
        norm: normLine,
        joinedStart,
        joinedEnd,
      })
      joinedParts.push(normLine)
      runningJoined = joinedEnd + 1 // space separator
    }
    if (m.index === lineRegex.lastIndex) lineRegex.lastIndex++
  }

  if (spans.length === 0) return null
  const joinedPageText = joinedParts.join(' ')

  function mapJoinedToPage(matchStart: number, matchEnd: number): { start: number; end: number } | null {
    let firstSpanIdx = -1
    let lastSpanIdx = -1
    for (let i = 0; i < spans.length; i++) {
      const sp = spans[i]
      if (sp.joinedEnd > matchStart && sp.joinedStart < matchEnd) {
        if (firstSpanIdx === -1) firstSpanIdx = i
        lastSpanIdx = i
      }
    }
    if (firstSpanIdx !== -1 && lastSpanIdx !== -1) {
      return {
        start: spans[firstSpanIdx].start,
        end: spans[lastSpanIdx].end,
      }
    }
    return null
  }

  // Tier 1: Exact Contiguous Match in joinedPageText
  const exactIdx = joinedPageText.indexOf(normTarget)
  if (exactIdx >= 0) {
    const range = mapJoinedToPage(exactIdx, exactIdx + normTarget.length)
    if (range) return range
  }

  // Check individual sentences if target is multi-sentence
  const targetSentences = normTarget.split(/(?<=[.!?।॥])\s+/).filter((s) => s.length >= 10)
  for (const sent of targetSentences) {
    const sIdx = joinedPageText.indexOf(sent)
    if (sIdx >= 0) {
      const range = mapJoinedToPage(sIdx, sIdx + sent.length)
      if (range) return range
    }
  }

  // Tier 2: Anchor Phrase Expansion (sliding 5-word or 4-word window)
  const targetWords = normTarget.split(/\s+/).filter(Boolean)
  let longestAnchor = ''
  let longestAnchorIdx = -1

  for (const winLen of [6, 5, 4, 3]) {
    if (targetWords.length >= winLen && !longestAnchor) {
      for (let i = 0; i <= targetWords.length - winLen; i++) {
        const anchor = targetWords.slice(i, i + winLen).join(' ')
        const pos = joinedPageText.indexOf(anchor)
        if (pos >= 0) {
          longestAnchor = anchor
          longestAnchorIdx = pos
          break
        }
      }
    }
  }

  if (longestAnchor && longestAnchorIdx >= 0) {
    let leftBound = Math.max(
      joinedPageText.lastIndexOf('.', longestAnchorIdx),
      joinedPageText.lastIndexOf('!', longestAnchorIdx),
      joinedPageText.lastIndexOf('?', longestAnchorIdx)
    )
    leftBound = leftBound === -1 ? 0 : leftBound + 1

    let rightDot = joinedPageText.indexOf('.', longestAnchorIdx + longestAnchor.length)
    let rightExcl = joinedPageText.indexOf('!', longestAnchorIdx + longestAnchor.length)
    let rightQuest = joinedPageText.indexOf('?', longestAnchorIdx + longestAnchor.length)
    const rightCandidates = [rightDot, rightExcl, rightQuest].filter((idx) => idx !== -1)
    const rightBound = rightCandidates.length > 0 ? Math.min(...rightCandidates) + 1 : joinedPageText.length

    const range = mapJoinedToPage(leftBound, rightBound)
    if (range) return range
  }

  // Tier 3: Span-Window Fallback (1-4 span windows scored by Token Jaccard + LCS)
  const targetTokens = extractSignificantTokens(normTarget)
  if (targetTokens.length > 0) {
    let bestScore = -1
    let bestSpanRange: { start: number; end: number } | null = null

    for (let i = 0; i < spans.length; i++) {
      for (let k = 1; k <= 4 && i + k <= spans.length; k++) {
        const winJoined = spans.slice(i, i + k).map((s) => s.norm).join(' ')
        const winTokens = extractSignificantTokens(winJoined)
        if (winTokens.length === 0) continue

        let overlap = 0
        for (const tok of targetTokens) {
          if (winJoined.includes(tok)) overlap++
        }
        const recall = overlap / targetTokens.length
        const precision = overlap / winTokens.length
        let score = recall * 60.0 + precision * 25.0

        if (boldEntity && winJoined.includes(normalizeString(boldEntity))) {
          score += 40.0
        }

        if (recall >= 0.65 && score > bestScore) {
          bestScore = score
          bestSpanRange = {
            start: spans[i].start,
            end: spans[i + k - 1].end,
          }
        }
      }
    }
    if (bestSpanRange) return bestSpanRange
  }

  return null
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

  // 3.5. Multi-line code block or passage span matching (anchored by start & end lines)
  const normCleanText = clean
    .replace(/^```[a-zA-Z0-9+]*\s*/, '')
    .replace(/```$/, '')
    .replace(/[\u200b\u200c\u200d\ufeff\u2060\xad]/g, '')
    .trim()
  const rawLines = normCleanText.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length >= 3)
  if (rawLines.length >= 2) {
    const firstLine = rawLines[0]
    const lastLine = rawLines[rawLines.length - 1] === '}' && rawLines.length > 2
      ? rawLines[rawLines.length - 2]
      : rawLines[rawLines.length - 1]

    const firstLoc = locatePhraseInText(pageText, firstLine)
    if (firstLoc) {
      // Check if there is a program/code header immediately before firstLoc (e.g. "C++ Program: ...", "Implementation", "C++ Demo: ...")
      let candidateStart = firstLoc.start
      const textBefore = pageText.slice(0, firstLoc.start)
      const headerMatch = textBefore.match(/(?:(?:C\+\+|C|Python|Java|SQL)?\s*(?:Program|Demo|Implementation|Script|Baseline|Modified\s+Program|Version\s+\d+)[^\r\n]*)\s*$/i)
      if (headerMatch && headerMatch[0]) {
        const headerOffset = textBefore.lastIndexOf(headerMatch[0].trim())
        if (headerOffset >= 0 && firstLoc.start - headerOffset < 150) {
          candidateStart = headerOffset
        }
      }

      const restPage = pageText.slice(firstLoc.start)
      const lastLoc = locatePhraseInText(restPage, lastLine)
      if (lastLoc && lastLoc.end > 0) {
        let candidateEnd = firstLoc.start + lastLoc.end
        // If code has a closing brace '}' after lastLine, include it and stop cleanly
        const trailingSlice = pageText.slice(candidateEnd, candidateEnd + 40)
        const braceMatch = trailingSlice.match(/^[\s\r\n]*\}/)
        if (braceMatch) {
          candidateEnd += braceMatch[0].length
        }

        const targetTokens = extractSignificantTokens(normCleanText)
        if (targetTokens.length > 0) {
          const sliceText = pageText.slice(candidateStart, candidateEnd).toLowerCase()
          let matchesCount = 0
          for (const tok of targetTokens) {
            if (sliceText.includes(tok)) matchesCount++
          }
          if (matchesCount / targetTokens.length >= 0.35) {
            // Complete Code Block Highlighting: Balanced Brace Tracking across sibling functions
            const isCodeContent = /(?:#include|using\s+namespace|int\s+main|void\s+main|def\s+\w+|class\s+\w+|classify|cout\s*<<)/i.test(normCleanText) ||
                                  /(?:#include|using\s+namespace|int\s+main|classify)/i.test(pageText.slice(candidateStart, candidateStart + 300))
            if (isCodeContent) {
              let depth = 0
              let foundOpen = false
              let codeEnd = candidateStart
              for (let idx = candidateStart; idx < pageText.length; idx++) {
                const ch = pageText[idx]
                if (ch === '{') {
                  depth++
                  foundOpen = true
                } else if (ch === '}') {
                  depth--
                  if (foundOpen && depth === 0) {
                    codeEnd = idx + 1
                    const lookAhead = pageText.slice(idx + 1, idx + 140)
                    if (!/(?:int\s+main|void\s+main|string\s+\w+|bool\s+\w+|double\s+\w+|long\s+long\s+\w+)/i.test(lookAhead)) {
                      if (codeEnd >= candidateEnd) break
                    }
                  }
                }
              }
              if (codeEnd > candidateEnd) {
                candidateEnd = codeEnd
              }
            }
            return { start: candidateStart, end: candidateEnd }
          }
        }
      }
    }
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
      const rx = new RegExp(`(^|\\s|\\b)(${pattern})($|\\s|\\b)`, 'iu')
      const match = rx.exec(normPage) || rx.exec(pageText)
      if (match && match[2]) {
        const offset = match.index + match[0].indexOf(match[2])
        return { start: offset, end: offset + match[2].length }
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

const COMMON_STOPWORDS = new Set([
  'the', 'is', 'at', 'of', 'in', 'and', 'to', 'was', 'were', 'for', 'on', 'with', 'as',
  'by', 'an', 'be', 'this', 'that', 'which', 'from', 'or', 'are', 'it', 'its', 'formed',
  'under', 'document', 'based', 'according', 'provided', 'context', 'answer', 'question',
  'aim', 'experiment', 'section', 'what', 'who', 'how', 'why', 'when', 'where'
])

function extractSignificantTokens(text: string): string[] {
  return (text || '')
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter((w) => w.length >= 2 && !COMMON_STOPWORDS.has(w))
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

  const qLower = (activeQuery || '').toLowerCase()
  const aLower = (activeAnswer || '').toLowerCase()

  const isSupervisorIntent = /(?:supervis(?:ion|or|ed)|guided|mentor|faculty|instructor|under\s+the\s+supervision|किसकी\s+देखरेख|देखरेख|पर्यवेक्षक|मार्गदर्शक|सुपरवाइजर|निर्देशन|अधीन|kiske\s+supervision|kiski\s+dekhrekh)/i.test(qLower) ||
    /(?:under\s+the\s+supervision|supervised\s+by|faculty\s+supervisor)/i.test(aLower)

  const isSubmitterIntent = !isSupervisorIntent && (/(?:submitted\s+by|who\s+submitted|submitted|author|student|prepared\s+by|created\s+by|who\s+wrote|who\s+authored|name\s+of\s+student|roll\s+no|enrollment|किसने\s+जमा|जमा\s+किया|जमाकर्ता|किसका|किसने\s+बनाया|किसने\s+लिखा|विद्यार्थी|छात्र|kisne\s+submit|kiska\s+hai)/i.test(qLower) ||
    /(?:submitted\s+by|prepared\s+by|presented\s+by|authored\s+by)/i.test(aLower))

  // 0. Extract verbatim text inside the > **Supporting Evidence [k]:** blockquote
  if (activeAnswer) {
    const evBlockMatch = activeAnswer.match(/>\s*(?:\*\*)?Supporting\s+Evidence(?:\s*\[\d+\])?:?(?:\*\*)?\s*\n*>*\s*([\s\S]*?)(?=\n\s*\n\s*[^>]|$)/i)
    if (evBlockMatch && evBlockMatch[1]) {
      const cleanEv = evBlockMatch[1]
        .replace(/^>\s*/gm, '')
        .replace(/\*\*/g, '')
        .trim()
      if (cleanEv.length >= 5 && !candidates.includes(cleanEv)) {
        candidates.unshift(cleanEv)
        const evLines = cleanEv.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length >= 4)
        for (const el of evLines) {
          if (!candidates.includes(el)) candidates.push(el)
        }
      }
    }
  }

  // 0.1 Check citation.evidence_span or citation.snippet
  const explicitSpan = (cit as any).evidence_span || cit.snippet
  if (explicitSpan && explicitSpan.trim().length >= 5) {
    const cleanSpan = explicitSpan.replace(/^\[(?:Section|Table|Doc)\s+Context:[^\]]*\]\s*/i, '').trim()
    if (!candidates.includes(cleanSpan)) {
      candidates.push(cleanSpan)
    }
  }

  // 0.2 Extract any bold text from activeAnswer (e.g. **KEY_ENTITY**)
  if (activeAnswer) {
    const boldMatches = Array.from(activeAnswer.matchAll(/\*\*([^*]+)\*\*/g))
      .map((m) => m[1].trim())
      .filter((b) => b.length >= 3 && !/^(?:supporting\s+evidence|aim|experiment|index)\b/i.test(b))
    for (const b of boldMatches) {
      if (!candidates.includes(b)) {
        candidates.push(b)
      }
    }
  }

  // 1. Universal Answer-Overlap & Exact Span Alignment (Zero Hardcoded Person Names)
  if (activeAnswer) {
    // 1.0 Extract any verbatim fenced code blocks from activeAnswer as top priority candidates
    const codeBlockMatch = activeAnswer.match(/```(?:[a-zA-Z0-9+]+)?\s*([\s\S]*?)```/)
    if (codeBlockMatch && codeBlockMatch[1].trim().length >= 10) {
      const extractedCode = codeBlockMatch[1].trim()
      if (!candidates.includes(extractedCode)) candidates.unshift(extractedCode)
    }

    const cleanAnswer = activeAnswer
      .replace(/(?:\[|【|［|\u3010|\uFF3B)\s*\d+\s*(?:\]|】|］|\u3011|\uFF3D)/g, '')
      .replace(/^\[LLM unavailable[^\]]*\]/i, '')
      .replace(/^(?:based\s+on\s+the\s+context|according\s+to\s+the\s+document)[,\s]*/i, '')
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

      const ansTokens = extractSignificantTokens(cleanAnswer)
      const qTokens = extractSignificantTokens(activeQuery || '')
      const poolSentences: string[] = []
      for (const src of candidatePool) {
        const sentences = src
          .split(/(?:\r?\n+|(?<=[.!?।॥])\s+)/)
          .map((s) => s.trim())
          .filter((s) => s.length >= 4)
        for (const s of sentences) {
          if (!poolSentences.includes(s)) poolSentences.push(s)
        }
      }

      const scoredSentences = poolSentences.map((sentence) => {
        const sLower = sentence.toLowerCase()
        let score = 0
        for (const tok of ansTokens) {
          if (sLower.includes(tok)) score += 3
        }
        for (const tok of qTokens) {
          if (sLower.includes(tok)) score += 1
        }
        if (cleanAnswer.length <= 60 && sLower.includes(cleanAnswer.toLowerCase())) {
          score += 15
        }
        for (const tok of ansTokens) {
          if (/^\d+$/.test(tok) && sLower.includes(tok)) score += 5
        }
        // Universal role-aware boost without hardcoded names
        if (isSupervisorIntent) {
          if (/under\s+the\s+supervision|supervised\s+by|faculty\s+supervisor|supervisor|guided\s+by/i.test(sentence)) {
            score += 25
          }
          if (/^submitted\s+by/i.test(sentence.trim())) {
            score -= 30
          }
        } else if (isSubmitterIntent) {
          if (/^submitted\s+by|author|student\s+name|roll\s+no/i.test(sentence.trim())) {
            score += 25
          }
          if (/under\s+the\s+supervision/i.test(sentence)) {
            score -= 30
          }
        }
        return { sentence, score }
      })

      scoredSentences.sort((a, b) => b.score - a.score)
      for (const item of scoredSentences) {
        if (item.score >= 3 && !candidates.includes(item.sentence)) {
          candidates.push(item.sentence)
        }
      }
    }
  }

  // 2. Structured Multi-line Entity patterns (fallback)
  for (const src of candidatePool) {
    if (isSupervisorIntent) {
      const supMatch = src.match(/(?:under\s+the\s+supervision\s+of|supervised\s+by|supervisor|guided\s+by|mentor|faculty\s+supervisor)[:\s]*\n*([^\r\n]+)/i)
      if (supMatch && supMatch[0]) {
        const fullBlock = supMatch[0].trim()
        if (fullBlock.length >= 6 && !candidates.includes(fullBlock)) {
          candidates.unshift(fullBlock)
        }
        if (supMatch[1] && !candidates.includes(supMatch[1].trim())) {
          candidates.push(supMatch[1].trim())
        }
      }
    } else if (isSubmitterIntent) {
      // Strictly match "Submitted by" (never bare "Submitted in..."), "Prepared by", "Presented by", "Author:", etc.
      // And capture the ENTIRE block including prefix AND author line/enrollment:
      const submittedBlockMatch = src.match(/(?:submitted\s+by|prepared\s+by|presented\s+by|authored\s+by|author[:\s]|student\s+name[:\s])[:\s]*\n*([^\r\n]+(?:\r?\n\s*\([0-9A-Za-z_-]+\))?)/i)
      if (submittedBlockMatch && submittedBlockMatch[0]) {
        const fullBlock = submittedBlockMatch[0].trim()
        if (fullBlock.length >= 6 && !candidates.includes(fullBlock)) {
          candidates.unshift(fullBlock)
        }
        if (submittedBlockMatch[1]) {
          const authorLine = submittedBlockMatch[1].trim()
          if (!candidates.includes(authorLine)) candidates.push(authorLine)
          const nameOnly = authorLine.replace(/\s*\([^\)]*\)/g, '').trim()
          if (nameOnly && nameOnly !== authorLine && nameOnly.length >= 3 && !candidates.includes(nameOnly)) {
            candidates.push(nameOnly)
          }
        }
      }
      const indexNameMatch = src.match(/(?:Index\s+Name|Student\s+Name|Name)[:\s]*([^\r\n]+?)(?:\s+Roll\s+No\.?[:\s]*(\d+))?(?:\s+Class|$)/i)
      if (indexNameMatch && indexNameMatch[0]) {
        const fullIndexBlock = indexNameMatch[0].trim()
        if (!candidates.includes(fullIndexBlock)) candidates.unshift(fullIndexBlock)
        if (indexNameMatch[1]) {
          const iName = indexNameMatch[1].trim()
          const iRoll = indexNameMatch[2] ? ` (${indexNameMatch[2].trim()})` : ''
          const fullSubmitter = `${iName}${iRoll}`
          if (!candidates.includes(fullSubmitter)) candidates.push(fullSubmitter)
          if (!candidates.includes(iName)) candidates.push(iName)
        }
      }
    } else {
      const submittedBlock = src.match(/(?:submitted\s+by|prepared\s+by|authored\s+by|author[:\s])[:\s]*\n*([^\r\n]+)/i)
      if (submittedBlock && submittedBlock[0]) {
        const fullBlock = submittedBlock[0].trim()
        if (fullBlock.length >= 6 && !candidates.includes(fullBlock)) candidates.push(fullBlock)
        if (submittedBlock[1] && !candidates.includes(submittedBlock[1].trim())) {
          candidates.push(submittedBlock[1].trim())
        }
      }
      const supMatch = src.match(/(?:under\s+the\s+supervision\s+of|supervised\s+by|supervisor|guided\s+by|mentor)[:\s]*\n*([^\r\n]+)/i)
      if (supMatch && supMatch[0]) {
        const fullBlock = supMatch[0].trim()
        if (fullBlock.length >= 6 && !candidates.includes(fullBlock)) candidates.push(fullBlock)
        if (supMatch[1] && !candidates.includes(supMatch[1].trim())) candidates.push(supMatch[1].trim())
      }
    }

    const aimMulti = src.match(/\baim[:\s]*\n*([^\r\n]+)/i)
    if (aimMulti && aimMulti[1]) {
      const aimText = aimMulti[1].trim()
      if (aimText.length >= 6 && !candidates.includes(aimText)) candidates.push(aimText)
    }
  }

  if (!fullText) return candidates

  // 3. Segment analysis from citation text (handling coalesced multi-chunk boundaries cleanly)
  // 3.0 Extract any verbatim program or code block inside citation text (strictly bounded up to closing brace or next section)
  const citCodeMatch = fullText.match(/(?:C\+\+\s*Program:?\s*[^\r\n]*\s*)?(?:#include|def\s|class\s|import\s)[\s\S]*?(?:\n\s*\}|\n\s*(?:Performance\s+Testing|Usability\s+Testing|Functional\s+Testing|Non-Functional\s+Testing|Test\s+Cases?|Compile:|Conclusion|Aim|Theory|\|\s*ID\s*\|)|$)/i)
  if (citCodeMatch && citCodeMatch[0].trim().length >= 15) {
    const extractedCitCode = citCodeMatch[0].trim()
    if (!candidates.includes(extractedCitCode)) candidates.push(extractedCitCode)
  }

  const chunkParts = fullText
    .split(/(?:\r?\n){2,}|\.\.\./)
    .map((p) => p.trim())
    .filter(Boolean)

  const rawSegments: string[] = []
  for (const part of chunkParts) {
    if (part.length >= 10 && part.length <= 400 && !candidates.includes(part)) {
      candidates.push(part)
    }
    const lines = part
      .split(/(?:\r?\n+|(?<=[.!?])\s+)/)
      .map((s) => s.trim())
      .filter((s) => s.length >= 6)
    rawSegments.push(...lines)
  }

  // Prioritize segments matching user query or key entity phrases
  if (activeQuery) {
    const qWords = activeQuery.toLowerCase().split(/\W+/).filter((w) => w.length > 2)
    const scored = rawSegments.map((seg) => {
      const segLower = seg.toLowerCase()
      let score = 0
      for (const w of qWords) {
        if (segLower.includes(w)) score += 3
      }
      if (isSubmitterIntent && /submitted\s+by|author|student|roll\s+no/i.test(seg)) {
        score += 10
      } else if (isSupervisorIntent && /under\s+the\s+supervision|supervised\s+by|supervisor/i.test(seg)) {
        score += 10
      } else if (/submitted\s+by|author|supervisor|prepared\s+by|aim|theory|total|section|liability|rule/i.test(seg)) {
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

  // Add individual snapped chunk parts rather than arbitrary joins
  for (const part of chunkParts) {
    const snapped = snapToWordBoundary(part, 120)
    if (snapped && !candidates.includes(snapped)) {
      candidates.push(snapped)
    }
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
  onPopOutPreview,
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
  const [citationJumpKey, setCitationJumpKey] = useState<number>(0)
  const prevCitRef = useRef<Citation | null>(null)

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
  }, [effectiveSessionId, activeDocument])

  // 2. Synchronize current page and trigger viewer jump when user selects a different citation
  useEffect(() => {
    if (activeCitation) {
      if (activeCitation !== prevCitRef.current) {
        prevCitRef.current = activeCitation
        setCitationJumpKey((k) => k + 1)
      }
      if (activeCitation.file === activeDocument && activeCitation.page != null && activeCitation.page > 0) {
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

  // Modality helpers & Image OCR safeguards
  const isImage = useMemo(() => {
    return (
      docContent?.modality === 'image' ||
      activeCitation?.modality === 'image' ||
      /\.(png|jpe?g|webp|bmp|gif|svg)$/i.test(activeDocument || '')
    )
  }, [docContent?.modality, activeCitation?.modality, activeDocument])

  const imageUrl = useMemo(() => {
    if (docContent?.raw_url) {
      const url = docContent.raw_url
      return url.includes('token=') ? url : `${url}?token=${encodeURIComponent(getToken())}`
    }
    if (activeCitation?.media_url) {
      const url = activeCitation.media_url
      return url.includes('token=') ? url : `${url}?token=${encodeURIComponent(getToken())}`
    }
    if (activeDocument && effectiveSessionId) {
      return `/api/media/${encodeURIComponent(effectiveSessionId)}/${encodeURIComponent(activeDocument)}?token=${encodeURIComponent(getToken())}`
    }
    return ''
  }, [docContent?.raw_url, activeCitation?.media_url, activeDocument, effectiveSessionId])

  const visualDescription = useMemo(() => {
    if (docContent?.caption) return docContent.caption
    const match = (docContent?.content || activeCitation?.text || activeCitation?.snippet || '').match(
      /(?:Visual Scene Description|Visual Description):\s*([^\n]+)/i
    )
    if (match && match[1] && !match[1].includes('Screenshot / Graphic')) return match[1].trim()
    return null
  }, [docContent?.caption, docContent?.content, activeCitation])

  const cleanOcrText = useMemo(() => {
    if (docContent?.ocr_text && docContent.ocr_text.trim()) return docContent.ocr_text.trim()
    const raw = docContent?.content || activeCitation?.text || activeCitation?.snippet || ''
    const stripped = raw
      .replace(/\[Image (?:File|Evidence):[^\]]+\]/gi, '')
      .replace(/Visual (?:Scene )?Description:[^\n]+/gi, '')
      .replace(/Text \/ Content visible inside the image:/gi, '')
      .replace(/Visible OCR Text in Image:/gi, '')
      .replace(/Detected Text \/ OCR:/gi, '')
      .trim()
    return stripped || ''
  }, [docContent?.ocr_text, docContent?.content, activeCitation])

  const safeOcrText = useMemo(() => {
    if (!cleanOcrText) return ''
    if (cleanOcrText.startsWith('‰PNG') || cleanOcrText.includes('IHDR') || cleanOcrText.includes('IDAT')) {
      return ''
    }
    const noiseGlyphs = new Set(['×', 'x', 'X', '+', '-', '□', '■', '←', '→', '↑', '↓', '①', '②', '③', '*', '•', '品', '回', '狗', '自', '|', '\\', '/', '>', '<', '~', '^', '_'])
    const lines = cleanOcrText.split('\n')
      .map(l => l.trim().replace(/\s+[×xX+□■]\s*$/, ''))
      .filter(l => l.length > 0 && !noiseGlyphs.has(l) && (l.length > 2 || /[a-zA-Z0-9]/.test(l)))
    return lines.join('\n')
  }, [cleanOcrText])

  const targetTextForHighlights = useMemo(() => {
    if (isImage) return safeOcrText
    return currentPageText
  }, [isImage, safeOcrText, currentPageText])

  // Text matching & Highlighting Engine (Unicode, Devanagari, and whitespace aware)
  const renderedTextWithHighlights = useMemo(() => {
    if (!targetTextForHighlights) return null

    // Find all citations on this page or without page restrictions
    const citationsOnThisPage = docCitations.filter(
      (c) => c.page === null || c.page === currentPage || (!docContent?.has_pages)
    )

    if (citationsOnThisPage.length === 0) {
      return <div className="whitespace-pre-wrap leading-relaxed text-surface-800 dark:text-surface-200">{targetTextForHighlights}</div>
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
      let matchFound = false

      // 1. Exact wrapped PDF sentence matching (1-to-3 consecutive line window scoring)
      let targetEv = (cit as any).evidence_span || cit.snippet || ''
      if (activeAnswer) {
        const evMatch = activeAnswer.match(/>\s*(?:\*\*)?Supporting\s+Evidence(?:\s*\[(\d+)\])?:?\*\*\s*\n*>*\s*([\s\S]*?)(?=\n\s*\n\s*[^>]|$)/i)
        if (evMatch && (!evMatch[1] || Number(evMatch[1]) === cit.index || cit.index === 1)) {
          const cleanBlock = evMatch[2].replace(/^>\s*/gm, '').replace(/\*\*/g, '').trim()
          if (cleanBlock.length >= 8) {
            targetEv = cleanBlock
          }
        }
      }

      let boldEntity = ''
      if (activeAnswer) {
        const boldMatches = Array.from(activeAnswer.matchAll(/\*\*([^*]+)\*\*/g))
          .map((m) => m[1].trim())
          .filter((b) => b.length >= 2 && !/^(?:supporting\s+evidence|aim|experiment|index)\b/i.test(b))
        if (boldMatches.length > 0) {
          boldEntity = boldMatches[0]
        }
      }

      if (targetEv) {
        const winLoc = findExactHighlightRange(targetTextForHighlights, targetEv, boldEntity)
        if (winLoc && winLoc.end > winLoc.start) {
          matches.push({
            start: winLoc.start,
            end: winLoc.end,
            citation: cit,
            isActive: activeCitation?.index === cit.index,
          })
          matchFound = true
        }
      }

      if (!matchFound) {
        const phrases = getCandidatePhrases(cit, activeQuery, activeAnswer, targetTextForHighlights)
        for (const phrase of phrases) {
          const loc = locatePhraseInText(targetTextForHighlights, phrase)
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
      }

      // Fallback: try first clean word-bounded segment of citation text or snippet
      if (!matchFound) {
        const rawTarget = (cit.text || cit.snippet || '').trim().replace(/\s+/g, ' ')
        const probe = snapToWordBoundary(rawTarget, 80)
        if (probe && probe.length >= 4) {
          const loc = locatePhraseInText(targetTextForHighlights, probe)
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
    }

    // If no match located, return plain text
    if (matches.length === 0) {
      return (
        <div className="whitespace-pre-wrap leading-relaxed text-surface-800 dark:text-surface-200 break-words font-sans">
          {targetTextForHighlights}
        </div>
      )
    }

    // Sort matches by start position
    matches.sort((a, b) => a.start - b.start)

    // Build segments
    const elements: React.ReactNode[] = []
    let lastIdx = 0

    matches.forEach((m, i) => {
      let mStart = m.start
      if (mStart < lastIdx) {
        if (m.end <= lastIdx) return
        mStart = lastIdx
      }

      if (mStart > lastIdx) {
        elements.push(
          <span key={`text-${lastIdx}-${mStart}`}>
            {targetTextForHighlights.slice(lastIdx, mStart)}
          </span>
        )
      }

      const highlightedSlice = targetTextForHighlights.slice(mStart, m.end)
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

    if (lastIdx < targetTextForHighlights.length) {
      elements.push(
        <span key={`text-end-${lastIdx}`}>
          {targetTextForHighlights.slice(lastIdx)}
        </span>
      )
    }

    return (
      <div className="whitespace-pre-wrap leading-relaxed text-surface-800 dark:text-surface-200 break-words font-sans">
        {elements}
      </div>
    )
  }, [targetTextForHighlights, docCitations, activeCitation, currentPage, docContent, activeQuery, activeAnswer])

  // Check if active citation has an exact verified match on current page
  const hasVerifiedMatchOnPage = useMemo(() => {
    if (!activeCitation || !targetTextForHighlights) return false
    let targetEv = (activeCitation as any).evidence_span || activeCitation.snippet || ''
    if (activeAnswer) {
      const evMatch = activeAnswer.match(/>\s*(?:\*\*)?Supporting\s+Evidence(?:\s*\[(\d+)\])?:?\*\*\s*\n*>*\s*([\s\S]*?)(?=\n\s*\n\s*[^>]|$)/i)
      if (evMatch && (!evMatch[1] || Number(evMatch[1]) === activeCitation.index || activeCitation.index === 1)) {
        const cleanBlock = evMatch[2].replace(/^>\s*/gm, '').replace(/\*\*/g, '').trim()
        if (cleanBlock.length >= 8) targetEv = cleanBlock
      }
    }
    let boldEntity = ''
    if (activeAnswer) {
      const boldMatches = Array.from(activeAnswer.matchAll(/\*\*([^*]+)\*\*/g))
        .map((m) => m[1].trim())
        .filter((b) => b.length >= 2 && !/^(?:supporting\s+evidence|aim|experiment|index)\b/i.test(b))
      if (boldMatches.length > 0) boldEntity = boldMatches[0]
    }
    if (targetEv && findExactHighlightRange(targetTextForHighlights, targetEv, boldEntity)) {
      return true
    }
    const phrases = getCandidatePhrases(activeCitation, activeQuery, activeAnswer, targetTextForHighlights)
    for (const p of phrases) {
      if (locatePhraseInText(targetTextForHighlights, p)) return true
    }
    const probe = (activeCitation.text || activeCitation.snippet || '').trim().slice(0, 60)
    return !!locatePhraseInText(currentPageText, probe)
  }, [activeCitation, currentPageText, targetTextForHighlights, activeQuery, activeAnswer])

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
          ) : isImage ? (
            <ImageIcon className="h-5 w-5 text-indigo-500 shrink-0" />
          ) : (
            <FileText className="h-5 w-5 text-brand-600 shrink-0" />
          )}

          <div className="min-w-0">
            <h3 className="truncate font-semibold text-sm text-surface-900 dark:text-surface-100" title={activeDocument}>
              {activeDocument}
            </h3>
            <div className="flex items-center gap-2 text-[11px] text-surface-500 dark:text-surface-400">
              <span className="uppercase font-mono font-medium">{isImage ? 'IMAGE' : (docContent?.modality || 'DOC')}</span>
              <span>&middot;</span>
              {docContent?.has_pages ? (
                <span className="font-medium text-brand-600 dark:text-brand-400">
                  Page {currentPage} of {totalPages}
                </span>
              ) : isImage ? (
                <span className="font-medium text-indigo-600 dark:text-indigo-400">Visual &amp; OCR Evidence</span>
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

          {/* Pop-up Modal Preview */}
          {onPopOutPreview && (
            <button
              type="button"
              onClick={() => onPopOutPreview(activeDocument, effectiveSessionId, currentPage)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-xs font-medium text-brand-600 dark:text-brand-400 hover:bg-surface-100 dark:hover:bg-surface-700 transition"
              title="Pop up document in full screen preview modal"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Pop-up Preview</span>
            </button>
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
              {activeCitation && !hasVerifiedMatchOnPage && !isImage && (
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-surface-800 dark:bg-surface-900">
                  <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
                    <Sparkles className="h-4 w-4 text-amber-500" />
                    <span>Verified Source Passage (Visual location fallback)</span>
                  </div>
                  <p className="text-xs text-surface-500 dark:text-surface-400 mb-2">
                    Exact character position could not be automatically anchored in page layout text. Displaying the exact retrieved source chunk below without fabrication:
                  </p>
                  <blockquote className="rounded-lg bg-surface-50 p-3 text-xs italic text-surface-800 border border-surface-200 dark:border-surface-800 dark:bg-surface-850 dark:text-surface-200 font-sans leading-relaxed whitespace-pre-wrap">
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
                    key={`pdf-obj-${docContent?.filename || activeDocument}-jump-${citationJumpKey}`}
                    data={`${docContent.raw_url}?token=${encodeURIComponent(getToken())}#page=${currentPage}`}
                    type="application/pdf"
                    className="w-full flex-1 border-0"
                    title={activeDocument}
                  >
                    <iframe
                      key={`pdf-iframe-${docContent?.filename || activeDocument}-jump-${citationJumpKey}`}
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
              ) : isImage ? (
                /* Dedicated Image & OCR Evidence Viewer */
                <div className="rounded-2xl border border-surface-200 bg-white shadow-sm overflow-hidden dark:border-surface-800 dark:bg-surface-900 flex flex-col">
                  {/* Image Canvas / Stage */}
                  <div className="relative flex flex-col items-center justify-center p-4 sm:p-6 bg-surface-100/70 dark:bg-surface-950/80 border-b border-surface-200 dark:border-surface-800 min-h-[340px] max-h-[640px] overflow-auto">
                    {imageUrl ? (
                      <AuthImage
                        url={imageUrl}
                        alt={activeDocument}
                        className="max-h-[560px] max-w-full rounded-lg object-contain shadow-md transition-transform duration-200 select-none cursor-zoom-in"
                        onClick={() => window.open(imageUrl, '_blank')}
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center p-8 text-surface-400">
                        <ImageIcon className="h-10 w-10 mb-2 opacity-50" />
                        <p className="text-xs">Image preview not available</p>
                      </div>
                    )}
                  </div>

                  {/* OCR & Visual Intelligence Section */}
                  <div className="p-6 space-y-6">
                    {/* Visual Scene Description Card if available */}
                    {visualDescription && (
                      <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-4 dark:border-indigo-900/60 dark:bg-indigo-950/20">
                        <div className="flex items-center gap-2 mb-2 text-indigo-700 dark:text-indigo-300 font-semibold text-xs tracking-wide uppercase">
                          <Sparkles className="h-4 w-4" />
                          <span>Visual Scene Description</span>
                        </div>
                        <p className="text-sm text-surface-800 dark:text-surface-200 leading-relaxed font-sans">
                          {visualDescription}
                        </p>
                      </div>
                    )}

                    {/* Detected Text & OCR Transcript */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold uppercase tracking-wider text-surface-500">
                            Visible OCR Text &amp; Labels
                          </span>
                          {safeOcrText && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400">
                              {safeOcrText.split('\n').filter(Boolean).length} lines detected
                            </span>
                          )}
                        </div>
                        {safeOcrText && (
                          <button
                            type="button"
                            onClick={() => navigator.clipboard.writeText(safeOcrText)}
                            className="text-xs text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1 font-medium"
                          >
                            <Copy className="h-3.5 w-3.5" />
                            <span>Copy Extracted Text</span>
                          </button>
                        )}
                      </div>

                      {safeOcrText ? (
                        <div
                          ref={textContainerRef}
                          className="rounded-xl border border-surface-200 bg-surface-50/50 p-5 font-mono text-xs leading-relaxed whitespace-pre-wrap break-words dark:border-surface-800 dark:bg-surface-850/50 text-surface-800 dark:text-surface-200 max-h-[380px] overflow-y-auto"
                        >
                          {renderedTextWithHighlights}
                        </div>
                      ) : (
                        <div className="rounded-xl border border-dashed border-surface-200 p-6 text-center dark:border-surface-800 text-surface-400 dark:text-surface-500 text-xs">
                          No readable text or typography was detected in this image. This source is primarily visual.
                        </div>
                      )}
                    </div>
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
