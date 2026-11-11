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

  // Split into code blocks vs regular blocks
  const blocks = text.split(/(```[\s\S]*?```)/g)

  return (
    <div className="space-y-3.5 text-sm leading-relaxed text-surface-800 dark:text-surface-200">
      {blocks.map((block, idx) => {
        if (block.startsWith('```') && block.endsWith('```')) {
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
  const lines = raw.slice(3, -3).trim().split('\n')
  const lang = lines[0].trim().toLowerCase()
  const code = lines.length > 1 && !lines[0].includes(' ') ? lines.slice(1).join('\n') : raw.slice(3, -3).trim()

  function handleCopy() {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-surface-200 dark:border-surface-800 bg-surface-900 text-surface-100 font-mono text-xs shadow-subtle">
      <div className="flex items-center justify-between px-4 py-2 border-b border-surface-800 bg-surface-950/80">
        <div className="flex items-center gap-2 text-surface-400">
          <Terminal className="h-3.5 w-3.5" />
          <span className="uppercase text-[11px] font-semibold">{lang || 'CODE'}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded px-2 py-1 text-surface-300 hover:text-white hover:bg-surface-800 transition-colors"
          title="Copy code"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
          <span className="text-[11px]">{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <div className="p-4 overflow-x-auto scroll-thin">
        <pre className="text-surface-200">
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

  function flushTable(k: number) {
    if (tableBuffer.length > 0) {
      elements.push(<MarkdownTable key={`tbl-${k}`} lines={tableBuffer} onCitationClick={onCitationClick} validIndexes={validIndexes} />)
      tableBuffer = []
    }
  }

  lines.forEach((line, i) => {
    const trimmed = line.trim()

    // Markdown Table detection: lines with multiple pipe delimiters
    if ((trimmed.startsWith('|') && trimmed.endsWith('|')) || (trimmed.includes('|') && trimmed.split('|').length >= 3)) {
      tableBuffer.push(trimmed)
      return
    } else {
      flushTable(i)
    }

    if (!trimmed) {
      return
    }

    // Heading level 1-3
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h4 key={i} className="text-sm font-bold text-surface-900 dark:text-surface-100 mt-4 mb-1">
          {renderInline(trimmed.slice(4), onCitationClick, validIndexes)}
        </h4>
      )
      return
    }
    if (trimmed.startsWith('## ')) {
      elements.push(
        <h3 key={i} className="text-base font-bold text-surface-900 dark:text-surface-100 mt-5 mb-1.5 border-b border-surface-200 dark:border-surface-800 pb-1">
          {renderInline(trimmed.slice(3), onCitationClick, validIndexes)}
        </h3>
      )
      return
    }
    if (trimmed.startsWith('# ')) {
      elements.push(
        <h2 key={i} className="text-lg font-bold text-surface-900 dark:text-surface-100 mt-6 mb-2">
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
  return <>{elements}</>
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

  // Row 0 is header, Row 1 is divider (|---|---|), Row 2+ are rows
  const parseRow = (r: string) =>
    r
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((c) => c.trim())

  const headers = parseRow(lines[0])
  const sepIdx = lines.findIndex((l, idx) => idx > 0 && /^\|?[-:\s|]+\|?$/.test(l.trim()))
  const dataLines = sepIdx > 0 ? lines.slice(sepIdx + 1) : lines.slice(1)
  const rows = dataLines
    .filter((l) => l.trim().length > 0 && !/^\|?[-:\s|]+\|?$/.test(l.trim()))
    .map(parseRow)

  return (
    <div className="my-3 overflow-x-auto rounded-xl border border-surface-200 dark:border-surface-800 shadow-subtle">
      <table className="w-full text-left text-xs border-collapse">
        <thead className="bg-surface-100 dark:bg-surface-800/80 border-b border-surface-200 dark:border-surface-800 text-surface-700 dark:text-surface-300 font-semibold">
          <tr>
            {headers.map((h, i) => (
              <th key={i} className="p-3">
                {renderInline(h, onCitationClick, validIndexes)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-100 dark:divide-surface-800/60 bg-white dark:bg-surface-900/60">
          {rows.map((row, rIdx) => (
            <tr key={rIdx} className="hover:bg-surface-50 dark:hover:bg-surface-800/30 transition-colors">
              {row.map((cell, cIdx) => (
                <td key={cIdx} className="p-3 text-surface-800 dark:text-surface-200">
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
          className="inline-flex items-center justify-center h-4 min-w-[16px] px-1 mx-0.5 rounded text-[10px] font-bold bg-brand-100 text-brand-700 hover:bg-brand-600 hover:text-white dark:bg-brand-950 dark:text-brand-300 dark:hover:bg-brand-600 transition-colors select-none align-baseline cursor-pointer shadow-2xs"
          title={`View supporting evidence source [${num}]`}
        >
          {num}
        </button>
      )
    }

    // Now format bold **bold**, inline code `code`, and italic *italic*
    return <span key={`txt-${idx}`}>{formatInlineMarkdown(part)}</span>
  })
}

function formatInlineMarkdown(text: string): React.ReactNode {
  // Bold **text**
  const boldParts = text.split(/(\*\*.*?\*\*)/g)
  return boldParts.map((bPart, bIdx) => {
    if (bPart.startsWith('**') && bPart.endsWith('**')) {
      return (
        <strong key={bIdx} className="font-semibold text-surface-900 dark:text-surface-100">
          {bPart.slice(2, -2)}
        </strong>
      )
    }
    // Inline code `code`
    const codeParts = bPart.split(/(`.*?`)/g)
    return codeParts.map((cPart, cIdx) => {
      if (cPart.startsWith('`') && cPart.endsWith('`')) {
        return (
          <code
            key={cIdx}
            className="rounded bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 font-mono text-[12px] text-brand-700 dark:text-brand-300"
          >
            {cPart.slice(1, -1)}
          </code>
        )
      }
      return cPart
    })
  })
}
