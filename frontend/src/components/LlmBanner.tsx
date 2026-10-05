import { Info } from 'lucide-react'

export default function LlmBanner() {
  return (
    <div className="flex items-start gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300 sm:px-6">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
      <p>
        <span className="font-semibold">LLM is offline.</span> Answers will be
        extractive until Ollama is running.{' '}
        <code className="rounded bg-amber-100 px-1 py-0.5 text-xs dark:bg-amber-500/20">ollama serve</code>
        , then refresh the status.
      </p>
    </div>
  )
}
