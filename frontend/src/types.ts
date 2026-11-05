// ---------------------------------------------------------------------------
// Shared TypeScript types — mirror the backend API contract.
// ---------------------------------------------------------------------------

export type Modality = 'document' | 'image' | 'audio'
export type ModalityFilter = 'all' | 'document' | 'image' | 'audio'

export interface Citation {
  index: number
  id: string
  file: string
  modality: Modality
  source_type: string
  page: number | null
  start: number | null
  end: number | null
  timestamp: string | null
  snippet: string
  media_url: string
  score: number
  // brief §19: relative min-max normalization across this answer's own
  // citations — NOT a calibrated probability. `confidence` is a
  // deprecated alias (identical value) kept only for backward
  // compatibility; new code should read relative_relevance.
  relative_relevance: number
  confidence: number
}

export interface Hit {
  id: string
  file: string
  modality: Modality
  source_type: string
  page: number | null
  start: number | null
  end: number | null
  timestamp: string | null
  snippet: string
  media_url: string
  score: number
  text?: string
  channel?: string
  session_id?: string | null
}

export interface HealthResponse {
  status: string
  device: string
  llm_model: string
  llm_available: boolean
  index: { text_items: number; image_items: number }
}

export interface LibraryFile {
  file: string
  modality: Modality
  chunks: number
  ingested_at: string
}

export interface IngestResultItem {
  file: string
  modality?: Modality
  chunks?: number
  error?: string
}

export interface IngestResponse {
  status: string
  ingested: IngestResultItem[]
  files: LibraryFile[]
}

export interface FilesResponse { files: LibraryFile[] }
export interface DeleteFileResponse { status: string; removed_chunks: number; files: LibraryFile[] }

export interface QueryResponse {
  answer: string
  citations: Citation[]
  retrieved: Hit[]
  used_llm: boolean
  faithfulness_warning?: boolean
}

export interface ImageQueryResponse extends QueryResponse {
  query_caption: string
  query_ocr: string
}

export interface AudioQueryResponse extends QueryResponse {
  transcript: string
  language?: string
}

export interface TranscribeResponse { text: string; language?: string }

export interface SourceDetail {
  id: string
  file: string
  modality: Modality
  source_type: string
  page: number | null
  chunk: number | null
  chunk_total: number | null
  start: number | null
  end: number | null
  timestamp: string | null
  full_text: string
  media_url: string
  metadata: Record<string, unknown>
}

// ---- Auth -----------------------------------------------------------------

export interface AuthUser { id: string; email: string }
export interface AuthResponse { token: string; user: AuthUser }

// ---- Sessions -------------------------------------------------------------

export interface SessionSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  file_count: number
}

/** A message as PERSISTED by the backend (restored when reopening a chat). */
export interface StoredMessage {
  role: 'user' | 'assistant'
  text: string
  citations?: Citation[]
  usedLlm?: boolean
  contextLabel?: string
  contextValue?: string
  ts?: string
}

export interface SessionDetail {
  id: string
  title: string
  created_at: string
  updated_at: string
  messages: StoredMessage[]
  files: LibraryFile[]
}

// ---- Frontend-only chat message model -------------------------------------

export type MessageRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: MessageRole
  text: string
  citations?: Citation[]
  usedLlm?: boolean
  faithfulnessWarning?: boolean
  contextLabel?: string
  contextValue?: string
  loading?: boolean
  /** Object URL of a user-uploaded image (image query) shown in the bubble. */
  imageUrl?: string
}

/** Query scope chosen in the composer: modality + specific files ([] = all). */
export interface Scope {
  modality: ModalityFilter
  files: string[]
}

// ---- Providers ------------------------------------------------------------

export type ProviderName = 'ollama' | 'gemini' | 'openai' | 'claude' | 'groq'

export interface ProviderStatus {
  name: ProviderName
  label: string
  local: boolean
  model: string
  has_key: boolean
  available: boolean
  supports_images: boolean
  supports_streaming: boolean
}

export interface ProvidersResponse {
  providers: ProviderStatus[]
  default: ProviderName
}

export interface ProviderModel {
  id: string
  name: string
  context_window?: number
}

export interface ProviderModelsResponse {
  provider: ProviderName
  models: ProviderModel[]
}

/** Backend-authoritative active-provider state (spec §51A). Never carries
 * the API key — only which provider/model will answer the next question. */
export interface ActiveProviderResponse {
  provider: ProviderName
  model: string
  mode: 'local' | 'cloud'
  status: 'active'
}


/** One chunk of the /api/query/stream Server-Sent Events response. */
export interface StreamMetrics {
  provider?: string
  requested_provider?: string
  model?: string
  streaming_enabled?: boolean
  ttft_ms?: number | null
  generation_time_ms?: number | null
  total_llm_time_ms?: number | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  tokens_per_second?: number | null
}
