import React from 'react'
import {
  FileText,
  MessageSquare,
  Sparkles,
  UploadCloud,
  ArrowUpRight,
  Server,
  Cloud,
  Clock,
  Layers,
  Image as ImageIcon,
  AudioLines,
  FolderOpen,
  Plus,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import type {
  HealthResponse,
  LibraryFile,
  SessionSummary,
  ActiveProviderResponse,
  AuthUser,
  AppView,
  Modality,
} from '../types'

export interface DashboardViewProps {
  user: AuthUser
  health: HealthResponse | null
  sessions: SessionSummary[]
  files: LibraryFile[]
  activeProvider: ActiveProviderResponse | null
  onStartChat: () => void
  onSelectSession: (id: string) => void
  onOpenUpload: () => void
  onNavigate: (view: AppView) => void
}

function ModalityIcon({ modality }: { modality: Modality }) {
  const cls = 'h-4 w-4 shrink-0'
  if (modality === 'image') return <ImageIcon className={`${cls} text-sky-500`} />
  if (modality === 'audio') return <AudioLines className={`${cls} text-amber-500`} />
  return <FileText className={`${cls} text-brand-500`} />
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  user,
  health,
  sessions,
  files,
  activeProvider,
  onStartChat,
  onSelectSession,
  onOpenUpload,
  onNavigate,
}) => {
  const isLocal = activeProvider?.mode === 'local'
  const textChunks = health?.index?.text_items ?? 0
  const imageChunks = health?.index?.image_items ?? 0
  const totalChunks = textChunks + imageChunks

  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto space-y-8">
      {/* Top Welcome & Status Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 pb-6 dark:border-surface-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
            Workspace Dashboard
          </h1>
          <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">
            Organization Workspace: <span className="font-mono text-surface-700 dark:text-surface-300 font-semibold">{user.org_id || 'default_org'}</span> &middot; Signed in as <span className="text-surface-700 dark:text-surface-300">{user.email}</span>
          </p>
        </div>

        <div>
          <Badge
            variant={isLocal ? 'success' : 'brand'}
            size="md"
            dot
            className="px-3 py-1.5"
          >
            {isLocal ? '100% On-Premise Processing Active' : 'Cloud AI Connected'}
          </Badge>
        </div>
      </div>

      {/* 4 Stat Cards (Derived strictly from genuine backend API data) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Indexed Documents */}
        <Card>
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-surface-500 dark:text-surface-400">
                Indexed Documents
              </p>
              <h3 className="mt-2 text-2xl font-bold text-surface-900 dark:text-surface-100">
                {files.length}
              </h3>
              <p className="mt-1 text-[11px] text-surface-400">
                Across active session library
              </p>
            </div>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-950/60 dark:text-brand-400">
              <FolderOpen className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        {/* Metric 2: Vector Chunks */}
        <Card>
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-surface-500 dark:text-surface-400">
                Vector Embeddings
              </p>
              <h3 className="mt-2 text-2xl font-bold text-surface-900 dark:text-surface-100">
                {totalChunks}
              </h3>
              <p className="mt-1 text-[11px] text-surface-400">
                {textChunks} text &middot; {imageChunks} visual
              </p>
            </div>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
              <Layers className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        {/* Metric 3: Conversations */}
        <Card>
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-surface-500 dark:text-surface-400">
                AI Conversations
              </p>
              <h3 className="mt-2 text-2xl font-bold text-surface-900 dark:text-surface-100">
                {sessions.length}
              </h3>
              <p className="mt-1 text-[11px] text-surface-400">
                Saved multi-turn sessions
              </p>
            </div>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-50 text-sky-600 dark:bg-sky-950/60 dark:text-sky-400">
              <MessageSquare className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        {/* Metric 4: Active Model */}
        <Card>
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-surface-500 dark:text-surface-400">
                Active Inference
              </p>
              <h3 className="mt-2 text-base font-bold text-surface-900 dark:text-surface-100 truncate max-w-[130px]">
                {activeProvider?.model || health?.llm_model || 'qwen3:4b'}
              </h3>
              <p className="mt-1 text-[11px] font-mono text-emerald-600 dark:text-emerald-400">
                {isLocal ? 'Offline (CUDA/CPU)' : 'Cloud API Transit'}
              </p>
            </div>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400">
              {isLocal ? <Server className="h-5 w-5" /> : <Cloud className="h-5 w-5" />}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions (privately.max style) */}
      <Card>
        <CardHeader className="py-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-brand-500" />
            <CardTitle className="text-sm">Quick Actions</CardTitle>
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
            Start a new conversation or ingest documents for knowledge retrieval
          </p>
        </CardHeader>
        <CardContent className="p-4 flex flex-wrap items-center gap-3">
          <Button
            variant="primary"
            size="md"
            icon={<Plus className="h-4 w-4" />}
            onClick={onStartChat}
          >
            Start AI Chat
          </Button>

          <Button
            variant="secondary"
            size="md"
            icon={<UploadCloud className="h-4 w-4" />}
            onClick={onOpenUpload}
          >
            Upload Documents
          </Button>

          <Button
            variant="outline"
            size="md"
            icon={<ArrowUpRight className="h-4 w-4" />}
            onClick={() => onNavigate('settings')}
          >
            Configure Providers
          </Button>
        </CardContent>
      </Card>

      {/* Two Column Grid: Recent Documents & Recent Conversations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents Table */}
        <Card>
          <CardHeader className="py-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FolderOpen className="h-4 w-4 text-brand-500" />
              <CardTitle className="text-sm">Recent Documents</CardTitle>
            </div>
            <button
              onClick={() => onNavigate('documents')}
              className="text-xs font-medium text-brand-600 hover:text-brand-500 dark:text-brand-400"
            >
              View all
            </button>
          </CardHeader>

          <CardContent className="p-0">
            {files.length === 0 ? (
              <div className="p-8 text-center text-xs text-surface-400">
                <FileText className="mx-auto mb-2 h-8 w-8 text-surface-300 dark:text-surface-600" />
                No documents uploaded yet in this workspace.
              </div>
            ) : (
              <ul className="divide-y divide-surface-100 dark:divide-surface-800">
                {files.slice(0, 5).map((f) => (
                  <li
                    key={f.file}
                    className="flex items-center justify-between px-5 py-3 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <ModalityIcon modality={f.modality} />
                      <div className="min-w-0">
                        <p className="truncate text-xs font-medium text-surface-800 dark:text-surface-200">
                          {f.file}
                        </p>
                        <p className="text-[11px] text-surface-400">
                          {f.chunks} chunks &middot; {f.modality}
                        </p>
                      </div>
                    </div>
                    <Badge variant="neutral" size="sm">
                      Indexed
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Recent Conversations List */}
        <Card>
          <CardHeader className="py-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-sky-500" />
              <CardTitle className="text-sm">Recent Conversations</CardTitle>
            </div>
            <button
              onClick={onStartChat}
              className="text-xs font-medium text-brand-600 hover:text-brand-500 dark:text-brand-400"
            >
              + New chat
            </button>
          </CardHeader>

          <CardContent className="p-0">
            {sessions.length === 0 ? (
              <div className="p-8 text-center text-xs text-surface-400">
                <MessageSquare className="mx-auto mb-2 h-8 w-8 text-surface-300 dark:text-surface-600" />
                No conversation history yet. Start your first session!
              </div>
            ) : (
              <ul className="divide-y divide-surface-100 dark:divide-surface-800">
                {sessions.slice(0, 5).map((s) => (
                  <li
                    key={s.id}
                    onClick={() => onSelectSession(s.id)}
                    className="flex items-center justify-between px-5 py-3 hover:bg-surface-50 dark:hover:bg-surface-800/50 cursor-pointer transition-colors"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-surface-800 dark:text-surface-200">
                        {s.title}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5 text-[11px] text-surface-400">
                        <Clock className="h-3 w-3" />
                        <span>{new Date(s.updated_at || s.created_at).toLocaleDateString()}</span>
                        <span>&middot;</span>
                        <span>{s.message_count} messages</span>
                      </div>
                    </div>
                    <ArrowUpRight className="h-4 w-4 text-surface-400 shrink-0" />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
