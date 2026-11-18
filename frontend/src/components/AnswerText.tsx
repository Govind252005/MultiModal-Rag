import React, { useState } from 'react'
import { Copy, Check, Terminal } from 'lucide-react'

export interface AnswerTextProps {
  text: string
  onCitationClick: (index: number) => void
  validIndexes?: Set<number>
}

export default function AnswerText({
  text,
  onCitationClick,
  validIndexes,
}: AnswerTextProps) {
  if (!text) return null

  // Split into code blocks vs regular blocks (supports in-flight streaming code blocks too)
  const blocks = text.split(/(```[\s\S]*?```|```[\s\S]*$)/g)

  return (
    <div className="space-y-3.5 text-sm leading-relaxed text-surface-800 dark:text-surface-200">
      {blocks.map((block, idx) => {
        if (block.startsWith('```')) {
          return <CodeBlock key={idx} raw={block} />
        }
        return (
          <MarkdownSegment
            key={idx}
            content={block}
            onCitationClick={onCitationClick}
            validIndexes={validIndexes}
          />
        )
      })}
    </div>
  )
}

function CodeBlock({ raw }: { raw: string }) {
  const [copied, setCopied] = useState(false)
  const isClosed = raw.length >= 6 && raw.endsWith('```')
  const body = isClosed ? raw.slice(3, -3) : raw.slice(3)
  const lines = body.split('\n')
  const firstLine = (lines[0] || '').trim().toLowerCase()
  const isLangTag = firstLine && !firstLine.includes(' ') && /^[a-z0-9_+#.-]+$/i.test(firstLine)
  const lang = isLangTag ? firstLine : ''
  const code = isLangTag && lines.length > 1 ? lines.slice(1).join('\n') : body.trim()

  function handleCopy() {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="my-3 overflow-hidden rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-900 text-surface-100 font-mono text-xs shadow-subtle">
      <div className="flex items-center justify-between px-3.5 py-1.5 border-b border-surface-800 bg-surface-950/90">
        <div className="flex items-center gap-2 text-surface-400">
          <Terminal className="h-3.5 w-3.5" />
          <span className="uppercase text-[11px] font-medium tracking-wider">{lang || 'CODE'}</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded px-2 py-0.5 text-surface-400 hover:text-white hover:bg-surface-800 transition-colors"
          title="Copy code block"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          <span className="text-[11px] font-mono">{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <div className="p-3.5 overflow-x-auto scroll-thin">
        <pre className="text-surface-200 font-mono text-xs leading-relaxed whitespace-pre">
          <code>{code}</code>
        </pre>
      </div>
    </div>
  )
}

function MarkdownSegment({
  content,
  onCitationClick,
  validIndexes,
}: {
  content: string
  onCitationClick: (index: number) => void
  validIndexes?: Set<number>
}) {
  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let tableBuffer: string[] = []
  let quoteBuffer: string[] = []

  function flushTable(k: number) {
    if (tableBuffer.length > 0) {
      elements.push(<MarkdownTable key={`tbl-${k}`} lines={tableBuffer} onCitationClick={onCitationClick} validIndexes={validIndexes} />)
      tableBuffer = []
    }
  }

  function flushQuote(k: number) {
    if (quoteBuffer.length > 0) {
      const quoteText = quoteBuffer.map((l) => l.replace(/^>\s?/, '')).join('\n')
      elements.push(
        <blockquote
          key={`quote-${k}`}
          className="my-3 rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50/70 dark:bg-surface-850/60 p-3 text-xs leading-relaxed text-surface-700 dark:text-surface-300"
        >
          {renderInline(quoteText, onCitationClick, validIndexes)}
        </blockquote>
      )
      quoteBuffer = []
    }
  }

  lines.forEach((line, i) => {
    const trimmed = line.trim()

    // Markdown Table detection: lines with multiple pipe delimiters
    if ((trimmed.startsWith('|') && trimmed.endsWith('|')) || (trimmed.includes('|') && trimmed.split('|').length >= 3)) {
      flushQuote(i)
      tableBuffer.push(trimmed)
      return
    } else {
      flushTable(i)
    }

    // Markdown Blockquote detection: lines starting with >
    if (trimmed.startsWith('>')) {
      quoteBuffer.push(trimmed)
      return
    } else {
      flushQuote(i)
    }

    if (!trimmed) {
      return
    }

    // Heading level 1-3
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h4 key={i} className="text-sm font-semibold tracking-tight text-surface-900 dark:text-surface-100 mt-4 mb-1">
          {renderInline(trimmed.slice(4), onCitationClick, validIndexes)}
        </h4>
      )
      return
    }
    if (trimmed.startsWith('## ')) {
      elements.push(
        <h3 key={i} className="text-base font-semibold tracking-tight text-surface-900 dark:text-surface-100 mt-5 mb-1.5 border-b border-surface-200 dark:border-surface-800 pb-1">
          {renderInline(trimmed.slice(3), onCitationClick, validIndexes)}
        </h3>
      )
      return
    }
    if (trimmed.startsWith('# ') && !trimmed.startsWith('#include') && !trimmed.startsWith('#define') && !trimmed.startsWith('#pragma')) {
      elements.push(
        <h2 key={i} className="text-lg font-bold tracking-tight text-surface-900 dark:text-surface-100 mt-6 mb-2">
          {renderInline(trimmed.slice(2), onCitationClick, validIndexes)}
        </h2>
      )
      return
    }

    // Bullet list items
    if (/^[-*•]\s+/.test(trimmed)) {
      const itemText = trimmed.replace(/^[-*•]\s+/, '')
      elements.push(
        <li key={i} className="ml-5 list-disc text-surface-800 dark:text-surface-200 my-0.5">
          {renderInline(itemText, onCitationClick, validIndexes)}
        </li>
      )
      return
    }

    // Numbered list items
    if (/^\d+\.\s+/.test(trimmed)) {
      const itemText = trimmed.replace(/^\d+\.\s+/, '')
      elements.push(
        <li key={i} className="ml-5 list-decimal text-surface-800 dark:text-surface-200 my-0.5">
          {renderInline(itemText, onCitationClick, validIndexes)}
        </li>
      )
      return
    }

    // Regular paragraph
    elements.push(
      <p key={i} className="my-1.5">
        {renderInline(line, onCitationClick, validIndexes)}
      </p>
    )
  })

  flushTable(lines.length)
  flushQuote(lines.length)
  return <>{elements}</>
}

function isDividerLine(line: string): boolean {
  const clean = line.replace(/[|\s:-]/g, '')
  return clean.length === 0 && line.includes('-')
}

function MarkdownTable({
  lines,
  onCitationClick,
  validIndexes,
}: {
  lines: string[]
  onCitationClick: (index: number) => void
  validIndexes?: Set<number>
}) {
  if (lines.length < 2) return null

  const parseRow = (r: string) =>
    r
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((c) => c.trim())

  const headers = parseRow(lines[0])
  const sepIdx = lines.findIndex((l, idx) => idx > 0 && isDividerLine(l))
  const dataLines = sepIdx > 0 ? lines.slice(sepIdx + 1) : lines.slice(1)
  const rows = dataLines
    .filter((l) => l.trim().length > 0 && !isDividerLine(l))
    .map(parseRow)

  return (
    <div className="my-3 overflow-x-auto rounded-lg border border-surface-200 dark:border-surface-800 shadow-subtle">
      <table className="w-full text-left text-xs border-collapse">
        <thead className="bg-surface-50 dark:bg-surface-850 border-b border-surface-200 dark:border-surface-800 text-surface-700 dark:text-surface-300 font-semibold font-mono">
          <tr>
            {headers.map((h, i) => (
              <th key={i} className="px-3.5 py-2.5">
                {renderInline(h, onCitationClick, validIndexes)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-100 dark:divide-surface-800/60 bg-white dark:bg-surface-900">
          {rows.map((row, rIdx) => (
            <tr key={rIdx} className="hover:bg-surface-50/80 dark:hover:bg-surface-850/40 transition-colors">
              {row.map((cell, cIdx) => (
                <td key={cIdx} className="px-3.5 py-2 text-surface-800 dark:text-surface-200">
                  {renderInline(cell, onCitationClick, validIndexes)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function renderInline(
  text: string,
  onCitationClick: (index: number) => void,
  _validIndexes?: Set<number>
): React.ReactNode {
  // Split by citations: [1], 【1】, ［1］, [citation: 1], [cite: 1], etc.
  const citationParts = text.split(/(?:\[|【|［)(?:citation:|cite:|source:)?\s*(\d+)\s*(?:\]|】|］)/gi)

  return citationParts.map((part, idx) => {
    const isCitation = idx % 2 === 1
    if (isCitation) {
      const num = parseInt(part, 10)
      return (
        <button
          key={`cit-${idx}`}
          type="button"
          onClick={() => onCitationClick(num)}
          aria-label={`View supporting evidence source citation ${num}`}
          className="inline-flex items-center justify-center font-mono text-[11px] font-semibold px-1.5 py-0.2 mx-0.5 rounded border border-brand-200 dark:border-brand-800 bg-brand-50 dark:bg-brand-950/70 text-brand-700 dark:text-brand-300 hover:bg-brand-600 hover:text-white dark:hover:bg-brand-600 transition-all select-none align-baseline cursor-pointer shadow-2xs"
          title={`View supporting evidence source [${num}]`}
        >
          {num}
        </button>
      )
    }

    return <span key={`txt-${idx}`}>{formatInlineMarkdown(part)}</span>
  })
}

function formatInlineMarkdown(text: string): React.ReactNode {
  const highlightParts = text.split(/(==.*?==|<mark>[\s\S]*?<\/mark>)/g)
  return highlightParts.map((hPart, hIdx) => {
    if (
      (hPart.startsWith('==') && hPart.endsWith('==') && hPart.length >= 4) ||
      (hPart.startsWith('<mark>') && hPart.endsWith('</mark>'))
    ) {
      const content = hPart.startsWith('==') ? hPart.slice(2, -2) : hPart.slice(6, -7)
      return (
        <mark
          key={`mark-${hIdx}`}
          className="bg-amber-100 text-amber-950 dark:bg-amber-950/60 dark:text-amber-200 px-1 py-0.5 rounded font-medium border-b border-amber-400 dark:border-amber-600"
        >
          {formatBoldAndCode(content)}
        </mark>
      )
    }
    return <React.Fragment key={`h-${hIdx}`}>{formatBoldAndCode(hPart)}</React.Fragment>
  })
}

function formatBoldAndCode(text: string): React.ReactNode {
  const boldParts = text.split(/(\*\*.*?\*\*)/g)
  return boldParts.map((bPart, bIdx) => {
    if (bPart.startsWith('**') && bPart.endsWith('**')) {
      return (
        <strong key={bIdx} className="font-semibold text-surface-900 dark:text-surface-100">
          {bPart.slice(2, -2)}
        </strong>
      )
    }
    const codeParts = bPart.split(/(`.*?`)/g)
    return codeParts.map((cPart, cIdx) => {
      if (cPart.startsWith('`') && cPart.endsWith('`')) {
        return (
          <code
            key={cIdx}
            className="rounded bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 font-mono text-[12px] text-surface-900 dark:text-surface-100 border border-surface-200 dark:border-surface-700"
          >
            {cPart.slice(1, -1)}
          </code>
        )
      }
      return cPart
    })
  })
}
