import { useEffect } from 'react'
import { X } from 'lucide-react'
import AuthImage from './AuthImage'

/**
 * Full-screen image popup. Accepts EITHER:
 *   - mediaUrl: an authenticated /api/media URL (fetched through AuthImage), or
 *   - src:      a plain object/data URL (e.g. a user-uploaded query image).
 * Click the backdrop or press Esc to close.
 */
export default function Lightbox({
  mediaUrl, src, alt, onClose,
}: {
  mediaUrl?: string
  src?: string
  alt?: string
  onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/85 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white transition hover:bg-white/20"
        title="Close (Esc)"
      >
        <X className="h-5 w-5" />
      </button>
      {alt && (
        <div className="absolute left-1/2 top-4 max-w-[80vw] -translate-x-1/2 truncate rounded-full bg-white/10 px-4 py-1.5 text-xs font-medium text-white">
          {alt}
        </div>
      )}
      <div className="max-h-full max-w-full" onClick={(e) => e.stopPropagation()}>
        {mediaUrl ? (
          <AuthImage
            url={mediaUrl}
            alt={alt}
            className="max-h-[88vh] max-w-[92vw] rounded-lg object-contain shadow-2xl"
          />
        ) : src ? (
          <img
            src={src}
            alt={alt ?? 'image'}
            className="max-h-[88vh] max-w-[92vw] rounded-lg object-contain shadow-2xl"
          />
        ) : null}
      </div>
    </div>
  )
}
