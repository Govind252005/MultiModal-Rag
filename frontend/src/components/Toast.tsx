import { useEffect } from 'react'
import { AlertTriangle, X } from 'lucide-react'

export default function Toast({
  message, onClose,
}: {
  message: string | null
  onClose: () => void
}) {
  useEffect(() => {
    if (!message) return
    const t = setTimeout(onClose, 6000)
    return () => clearTimeout(t)
  }, [message, onClose])

  if (!message) return null
  return (
    <div className="fixed top-4 right-4 z-[60] max-w-sm">
      <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 shadow-lg dark:border-red-500/30 dark:bg-red-500/10">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
        <p className="flex-1 text-sm text-red-800 dark:text-red-300">{message}</p>
        <button onClick={onClose} className="text-red-400 transition hover:text-red-600" aria-label="Dismiss">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
