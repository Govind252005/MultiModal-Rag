import { useEffect, useState } from 'react'
import { ImageOff, Loader2 } from 'lucide-react'
import * as api from '../api'

/**
 * Renders an image served by the authenticated /api/media endpoint.
 * The media route requires a Bearer token, so we fetch the bytes and turn
 * them into an object URL rather than using a plain <img src>.
 */
export default function AuthImage({
  url, alt, className, onClick,
}: {
  url: string
  alt?: string
  className?: string
  onClick?: () => void
}) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false
    setSrc(null)
    setFailed(false)
    api
      .getMediaUrl(url)
      .then((u) => {
        if (cancelled) {
          URL.revokeObjectURL(u)
          return
        }
        objectUrl = u
        setSrc(u)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url])

  if (failed) {
    return (
      <div className={`flex items-center justify-center bg-slate-100 text-slate-400 dark:bg-slate-800 ${className ?? ''}`}>
        <ImageOff className="h-5 w-5" />
      </div>
    )
  }
  if (!src) {
    return (
      <div className={`flex items-center justify-center bg-slate-100 dark:bg-slate-800 ${className ?? ''}`}>
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    )
  }
  return (
    <img
      src={src}
      alt={alt ?? 'source image'}
      onClick={onClick}
      className={className}
      loading="lazy"
    />
  )
}
