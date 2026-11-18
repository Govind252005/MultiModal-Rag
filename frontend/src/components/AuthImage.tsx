import { useEffect, useState } from 'react'
import { ImageOff, Loader2 } from 'lucide-react'
import * as api from '../api'

/**
 * Renders an image served by the authenticated /api/media endpoint.
 * Fetches bytes with Authorization header or query-token fallback.
 */
export default function AuthImage({
  url,
  alt,
  className = '',
  onClick,
}: {
  url: string
  alt?: string
  className?: string
  onClick?: () => void
}) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false
    setLoading(true)
    setFailed(false)
    setSrc(null)

    if (!url) {
      setLoading(false)
      setFailed(true)
      return
    }

    if (url.startsWith('blob:') || url.startsWith('data:')) {
      setSrc(url)
      setLoading(false)
      return
    }

    const resolvedUrl = (url.startsWith('/') || url.startsWith('http')) ? url : `/${url}`
    let safeUrl = resolvedUrl
    try {
      safeUrl = encodeURI(decodeURI(resolvedUrl))
    } catch {
      safeUrl = encodeURI(resolvedUrl)
    }

    api
      .getMediaUrl(safeUrl)
      .then((u) => {
        if (cancelled) {
          URL.revokeObjectURL(u)
          return
        }
        objectUrl = u
        setSrc(u)
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        // Fallback: try direct authenticated URL with query token
        const token = api.getToken()
        if (token && !safeUrl.includes('token=')) {
          const sep = safeUrl.includes('?') ? '&' : '?'
          const directUrl = `${safeUrl}${sep}token=${encodeURIComponent(token)}`
          setSrc(directUrl)
          setLoading(false)
        } else {
          setFailed(true)
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url])

  if (loading) {
    return (
      <div className={`flex items-center justify-center rounded-lg border border-surface-200 bg-surface-100 dark:border-surface-800 dark:bg-surface-850 ${className}`}>
        <Loader2 className="h-4 w-4 animate-spin text-surface-400" />
      </div>
    )
  }

  if (failed || !src) {
    return (
      <div
        className={`flex flex-col items-center justify-center rounded-lg border border-surface-200 bg-surface-50 p-2 text-surface-400 dark:border-surface-800 dark:bg-surface-850 ${className}`}
        title={alt || 'Visual preview unavailable'}
      >
        <ImageOff className="h-4 w-4 text-surface-400 mb-1" />
        <span className="font-mono text-[9px] text-surface-500 truncate max-w-[120px]">
          {alt || 'Visual chunk'}
        </span>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt ?? 'source image'}
      onClick={onClick}
      onError={() => setFailed(true)}
      className={className}
      loading="lazy"
    />
  )
}
