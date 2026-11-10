// ---------------------------------------------------------------------------
// Shared TypeScript types — mirror the backend API contract.
// ---------------------------------------------------------------------------

export type Modality = 'document' | 'image' | 'audio'
export type ModalityFilter = 'all' | 'document' | 'image' | 'audio'

export interface Citation {
  index: number
  id: string
  file: string
  session_id?: string
  modality: Modality
  source_type: string
  page: number | null
  start: number | null
  end: number | null
  timestamp: string | null
  snippet: string
  text?: string
  media_url: string
  score: number
  // brief §19: relative min-max normalization across this answer's own
  // citations — NOT a calibrated probability. `confidence` is a
  // deprecated alias (identical value) kept only for backward
  // compatibility; new code should read relative_relevance.
  relative_relevance: number
  confidence: number
}

export interface DocumentPage {
  page_number: number
  title?: string
  section?: string
  text: string
}

export interface DocumentSheet {
  page_number: number
  title: string
  rows: string[][]
}

export interface DocumentContentResponse {
  filename: string
  modality: 'pdf' | 'docx' | 'pptx' | 'xlsx' | 'text' | 'audio' | 'image'
  has_pages: boolean
  page_count: number | null
  pages?: DocumentPage[]
  sheets?: DocumentSheet[]
  content?: string
  raw_url: string
  file_size: number
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

export interface AuthUser {
  id: string
  email: string
  role?: 'admin' | 'user' | 'super_admin' | string
  org_id?: string
  created_at?: string
}
export interface AuthResponse { token: string; user: AuthUser }

export type AppView =
  | 'landing'
  | 'login'
  | 'register'
  | 'onboarding'
  | 'dashboard'
  | 'chat'
  | 'documents'
  | 'collections'
  | 'search'
  | 'settings'
  | 'admin'

export interface AdminUserRecord {
  id: string
  email: string
  role: string
  org_id: string
  status?: 'active' | 'disabled'
  created_at?: string
  disabled?: boolean
}

export interface AuditLogRecord {
  id: string
  timestamp: string
  action: string
  user_email: string
  user_id: string
  org_id: string
  details?: Record<string, any>
  ip?: string
}

export interface ManagedDocument {
  filename: string
  modality: string
  size_bytes: number
  page_count: number
  chunk_count: number
  status: 'indexed' | 'pending' | 'processing' | 'failed' | string
  created_at: string
  collections: string[]
  session_id: string
}

export interface ManagedCollection {
  id: string
  name: string
  description: string
  owner_id: string
  org_id: string
  files: string[]
  file_count: number
  is_shared: boolean
  created_at: string
  updated_at: string
}

export interface OllamaDaemonStatus {
  status: string
  is_online: boolean
  latency_ms: number
  default_model: string
  models: Array<{ name: string; size?: number; modified_at?: string }>
}

export interface EmbeddingMetadata {
  dense_model: string
  dense_dimension: number
  clip_model: string
  clip_dimension: number
}

export interface SecurityEventRecord {
  timestamp: string
  event: string
  user_id?: string
  ip?: string
  details?: string
  org_id?: string
}

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
  metrics?: StreamMetrics
  provider?: string
  model?: string
}

/** Query scope chosen in the composer: modality + specific files ([] = all). */
export interface Scope {
  modality: ModalityFilter
  files: string[]
  collection_id?: string
  collection_name?: string
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
  retrieval_ms?: number | null
  generation_ms?: number | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  tokens_per_second?: number | null
  faithfulness_score?: number | null
}
