import { useEffect } from 'react'
import { AlertCircle, MicOff, X } from 'lucide-react'

export default function Toast({
  message,
  onClose,
}: {
  message: string | null
  onClose: () => void
}) {
  useEffect(() => {
    if (!message) return
    const t = setTimeout(onClose, 5000)
    return () => clearTimeout(t)
  }, [message, onClose])

  if (!message) return null

  const isMic =
    message.toLowerCase().includes('microphone') ||
    message.toLowerCase().includes('mic')

  return (
    <div className="fixed bottom-6 left-6 z-[70] max-w-sm animate-in slide-in-from-bottom-3 fade-in duration-200">
      <div className="flex items-center gap-3 rounded-xl border border-surface-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur-md dark:border-surface-700 dark:bg-surface-900/95 text-surface-900 dark:text-surface-100">
        {isMic ? (
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400">
            <MicOff className="h-4 w-4" />
          </div>
        ) : (
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-rose-50 text-rose-600 dark:bg-rose-950/50 dark:text-rose-400">
            <AlertCircle className="h-4 w-4" />
          </div>
        )}
        <div className="flex-1 min-w-0 pr-1">
          <p className="text-xs font-semibold leading-snug">{message}</p>
        </div>
        <button
          onClick={onClose}
          className="text-surface-400 hover:text-surface-600 dark:hover:text-surface-200 p-1 rounded-md transition"
          aria-label="Dismiss"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
