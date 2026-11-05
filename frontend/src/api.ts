// ---------------------------------------------------------------------------
// Centralized API client with token auth. Every request carries the logged-in
// user's Bearer token, so the backend scopes all data to that user.
// ---------------------------------------------------------------------------

import type {
  HealthResponse, IngestResponse, FilesResponse, DeleteFileResponse,
  QueryResponse, ImageQueryResponse, AudioQueryResponse, TranscribeResponse,
  SourceDetail, ModalityFilter, SessionSummary, SessionDetail,
  AuthUser, AuthResponse, ProvidersResponse, ProviderName,
  ActiveProviderResponse, Citation, StreamMetrics,
  ProviderModelsResponse,
} from './types'



// ---- token -----------------------------------------------------------------
let TOKEN = ''
try { TOKEN = localStorage.getItem('token') || '' } catch { /* ignore */ }

export function setToken(t: string) {
  TOKEN = t
  try { localStorage.setItem('token', t) } catch { /* ignore */ }
}
export function clearToken() {
  TOKEN = ''
  try { localStorage.removeItem('token') } catch { /* ignore */ }
}
export function hasToken() { return !!TOKEN }

// ---- core fetch ------------------------------------------------------------
async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (TOKEN) headers.set('Authorization', `Bearer ${TOKEN}`)

  let res: Response
  try {
    res = await fetch(url, { ...init, headers })
  } catch (err) {
    throw new Error(`Cannot reach the backend. Is the server running? (${(err as Error).message})`)
  }

  const isAuthRequest = url === '/api/auth/login' || url === '/api/auth/register'
  if (res.status === 401 && !isAuthRequest) {
    // Token missing/expired — force re-login.
    clearToken()
    window.dispatchEvent(new CustomEvent('auth-expired'))
    throw new Error('Your session expired. Please log in again.')
  }
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body?.detail || body?.error?.message || body?.error || JSON.stringify(body)
    } catch { detail = await res.text().catch(() => '') }
    throw new Error(`Request failed (${res.status}): ${detail || res.statusText}`)
  }
  return (await res.json()) as T
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// ---- auth ------------------------------------------------------------------
export const register = (email: string, password: string) =>
  request<AuthResponse>('/api/auth/register', json({ email, password }))

export const login = (email: string, password: string) =>
  request<AuthResponse>('/api/auth/login', json({ email, password }))

export const me = () => request<{ user: AuthUser }>('/api/auth/me').then((r) => r.user)

export async function logout(): Promise<void> {
  try {
    await request<{ status: string }>('/api/auth/logout', { method: 'POST' })
  } finally {
    // Always clear the local token even if the revocation call itself
    // failed (e.g. already expired) — the person should never be stuck
    // "logged in" locally after asking to log out.
    clearToken()
  }
}

// ---- health ----------------------------------------------------------------
export const health = () => request<HealthResponse>('/api/health')

// ---- sessions --------------------------------------------------------------
export const listSessions = () =>
  request<{ sessions: SessionSummary[] }>('/api/sessions').then((r) => r.sessions)
export const createSession = (title = 'New chat') =>
  request<SessionDetail>('/api/sessions', json({ title }))
export const getSession = (id: string) =>
  request<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`)
export const renameSession = (id: string, title: string) =>
  request<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
export const deleteSession = (id: string) =>
  request<{ status: string }>(`/api/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' })

// ---- ingestion -------------------------------------------------------------
export function ingest(sessionId: string, files: File[]): Promise<IngestResponse> {
  const form = new FormData()
  form.append('session_id', sessionId)
  for (const f of files) form.append('files', f)
  return request<IngestResponse>('/api/ingest', { method: 'POST', body: form })
}
export const listFiles = (sessionId: string) =>
  request<FilesResponse>(`/api/files?session_id=${encodeURIComponent(sessionId)}`)
export const deleteFile = (sessionId: string, name: string) =>
  request<DeleteFileResponse>(
    `/api/files/${encodeURIComponent(name)}?session_id=${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' })

// ---- querying --------------------------------------------------------------
export function query(sessionId: string, q: string, topK: number,
                      modality: ModalityFilter, files: string[],
                      provider?: ProviderName): Promise<QueryResponse> {
  return request<QueryResponse>('/api/query', json({
    session_id: sessionId, query: q, top_k: topK, modality,
    files: files.length ? files : null,
    provider: provider ?? null,
  }))
}
export function queryImage(sessionId: string, file: File, topK: number, files: string[],
                           provider?: ProviderName): Promise<ImageQueryResponse> {
  const form = new FormData()
  form.append('session_id', sessionId); form.append('file', file); form.append('top_k', String(topK))
  if (files.length) form.append('files', files.join(','))
  if (provider) form.append('provider', provider)
  return request<ImageQueryResponse>('/api/query/image', { method: 'POST', body: form })
}
export function queryAudio(sessionId: string, file: File, topK: number, files: string[],
                           provider?: ProviderName): Promise<AudioQueryResponse> {
  const form = new FormData()
  form.append('session_id', sessionId); form.append('file', file); form.append('top_k', String(topK))
  if (files.length) form.append('files', files.join(','))
  if (provider) form.append('provider', provider)
  return request<AudioQueryResponse>('/api/query/audio', { method: 'POST', body: form })
}
export function transcribe(sessionId: string, blob: Blob): Promise<TranscribeResponse> {
  const form = new FormData()
  form.append('session_id', sessionId); form.append('file', blob, 'recording.webm')
  return request<TranscribeResponse>('/api/transcribe', { method: 'POST', body: form })
}

// ---- streaming text query (SSE) --------------------------------------------
// /api/query/stream can't use the plain EventSource API (it needs a POST
// body and a Bearer header, neither of which EventSource supports), so this
// parses the "event: ...\ndata: ...\n\n" frames off the raw fetch body
// stream by hand. Same request shape/semantics as query() above — citations
// and provider/history resolution are identical; only the answer arrives
// token-by-token instead of all at once.
export interface QueryStreamCallbacks {
  onCitations?: (citations: Citation[]) => void
  onDelta?: (text: string) => void
  onDone?: (info: { used_llm: boolean; metrics: StreamMetrics }) => void
  onError?: (err: Error) => void
}

export async function queryStream(
  sessionId: string, q: string, topK: number,
  modality: ModalityFilter, files: string[],
  provider: ProviderName | undefined,
  callbacks: QueryStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  if (TOKEN) headers.set('Authorization', `Bearer ${TOKEN}`)

  let res: Response
  try {
    res = await fetch('/api/query/stream', {
      method: 'POST',
      headers,
      signal,
      body: JSON.stringify({
        session_id: sessionId, query: q, top_k: topK, modality,
        files: files.length ? files : null, provider: provider ?? null,
      }),
    })
  } catch (err) {
    callbacks.onError?.(new Error(
      `Cannot reach the backend. Is the server running? (${(err as Error).message})`))
    return
  }

  if (res.status === 401) {
    clearToken()
    window.dispatchEvent(new CustomEvent('auth-expired'))
    callbacks.onError?.(new Error('Your session expired. Please log in again.'))
    return
  }
  if (!res.ok || !res.body) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body?.detail || body?.error?.message || body?.error || JSON.stringify(body)
    } catch {
      detail = await res.text().catch(() => '')
    }
    callbacks.onError?.(new Error(`Request failed (${res.status}): ${detail || res.statusText}`))
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let sep: number
      // SSE frames are separated by a blank line.
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)

        let eventName = 'message'
        let dataLine = ''
        for (const line of rawEvent.split('\n')) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          else if (line.startsWith('data:')) dataLine += line.slice(5).trim()
        }
        if (!dataLine) continue

        let payload: unknown
        try {
          payload = JSON.parse(dataLine)
        } catch {
          continue
        }

        if (eventName === 'citations') {
          callbacks.onCitations?.(payload as Citation[])
        } else if (eventName === 'delta') {
          const text = (payload as { text?: string }).text
          if (text) callbacks.onDelta?.(text)
        } else if (eventName === 'done') {
          callbacks.onDone?.(payload as { used_llm: boolean; metrics: StreamMetrics })
        }
      }
    }
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      callbacks.onError?.(err as Error)
    }
  }
}

// ---- sources ---------------------------------------------------------------
export const getSource = (id: string) =>
  request<SourceDetail>(`/api/source/${encodeURIComponent(id)}`)

// ---- providers -------------------------------------------------------------
export const getProviders = () =>
  request<ProvidersResponse>('/api/providers')

export const setProviderKey = (provider: ProviderName, apiKey: string) =>
  request<{ status: string; provider: string; has_key: boolean }>(
    '/api/providers/key', json({ provider, api_key: apiKey }))

export const deleteProviderKey = (provider: ProviderName) =>
  request<{ status: string; provider: string; has_key: boolean }>(
    `/api/providers/key/${encodeURIComponent(provider)}`, { method: 'DELETE' })

export const validateProviderKey = (provider: ProviderName, apiKey: string) =>
  request<{ provider: string; valid: boolean }>(
    '/api/providers/validate', json({ provider, api_key: apiKey }))

export const getProviderModels = (provider: ProviderName) =>
  request<ProviderModelsResponse>(`/api/providers/${encodeURIComponent(provider)}/models`)

// ---- active provider (spec §51A) -------------------------------------------
// Backend-authoritative "which provider actually answers the next question"
// state. Testing/storing a key (above) never changes this by itself — only
// an explicit call to activateProvider() does.
export const getActiveProvider = () =>
  request<ActiveProviderResponse>('/api/llm/active')

export const activateProvider = (provider: ProviderName, model?: string) =>
  request<ActiveProviderResponse>(
    `/api/llm/providers/${encodeURIComponent(provider)}/activate`,
    model ? json({ model }) : { method: 'POST' })


// ---- media ---------------------------------------------------------------
export async function getMediaUrl(url: string): Promise<string> {
  const headers = new Headers();

  if (TOKEN) {
    headers.set("Authorization", `Bearer ${TOKEN}`);
  }

  const res = await fetch(url, { headers });

  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new CustomEvent("auth-expired"));
    throw new Error("Your session expired.");
  }

  if (!res.ok) {
    throw new Error(`Failed to load media (${res.status})`);
  }

  const blob = await res.blob();

  return URL.createObjectURL(blob);
}