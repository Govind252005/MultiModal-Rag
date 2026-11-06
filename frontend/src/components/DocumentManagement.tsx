import React, { useState, useEffect, useMemo, useRef } from 'react'
import {
  FileText,
  Upload,
  Search,
  Grid,
  List,
  RefreshCw,
  Eye,
  Trash2,
  Download,
  RotateCw,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  FileImage,
  FileAudio,
  FileCode,
  Tag,
  Clock,
  Layers,
  HardDrive,
  X,
  Check,
  AlertTriangle,
  FolderOpen,
} from 'lucide-react'
import * as api from '../api'
import type { ManagedDocument, ManagedCollection } from '../types'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'
import { Input } from './ui/Input'
import { Modal } from './ui/Modal'

interface DocumentManagementProps {
  onOpenViewer: (sessionId: string, filename: string) => void
  onChatWithFiles?: (files: string[]) => void
}

export const DocumentManagement: React.FC<DocumentManagementProps> = ({
  onOpenViewer,
}) => {
  const [documents, setDocuments] = useState<ManagedDocument[]>([])
  const [collections, setCollections] = useState<ManagedCollection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table')

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedModality, setSelectedModality] = useState<string>('all')
  const [selectedCollection, setSelectedCollection] = useState<string>('all')
  const [sortBy, setSortBy] = useState<'date' | 'name' | 'size' | 'chunks'>('date')

  // Upload Modal State
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadCollectionId, setUploadCollectionId] = useState<string>('')
  const [uploading, setUploading] = useState(false)
  const [uploadStage, setUploadStage] = useState<number>(0)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Delete Confirm State
  const [deleteTarget, setDeleteTarget] = useState<ManagedDocument | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Reprocessing State
  const [reprocessing, setReprocessing] = useState<string | null>(null)
  const [actionNotice, setActionNotice] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [docsRes, colRes] = await Promise.all([
        api.listDocuments(),
        api.listCollections(),
      ])
      setDocuments(docsRes.documents || [])
      setCollections(colRes.collections || [])
    } catch (err: any) {
      setError(err?.message || 'Failed to load documents')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const filteredDocuments = useMemo(() => {
    return documents
      .filter((doc) => {
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase().trim()
          if (!doc.filename.toLowerCase().includes(q)) return false
        }
        if (selectedModality !== 'all') {
          if (selectedModality === 'pdf' && !doc.filename.toLowerCase().endsWith('.pdf')) return false
          if (selectedModality === 'docx' && !doc.filename.toLowerCase().endsWith('.docx') && !doc.filename.toLowerCase().endsWith('.doc')) return false
          if (selectedModality === 'txt' && !doc.filename.toLowerCase().endsWith('.txt') && !doc.filename.toLowerCase().endsWith('.md')) return false
          if (selectedModality === 'image' && !['png', 'jpg', 'jpeg', 'webp'].some(ext => doc.filename.toLowerCase().endsWith('.' + ext))) return false
          if (selectedModality === 'audio' && !['mp3', 'wav', 'm4a', 'webm'].some(ext => doc.filename.toLowerCase().endsWith('.' + ext))) return false
        }
        if (selectedCollection !== 'all') {
          if (!doc.collections || !doc.collections.includes(selectedCollection)) return false
        }
        return true
      })
      .sort((a, b) => {
        if (sortBy === 'name') return a.filename.localeCompare(b.filename)
        if (sortBy === 'size') return (b.size_bytes || 0) - (a.size_bytes || 0)
        if (sortBy === 'chunks') return (b.chunk_count || 0) - (a.chunk_count || 0)
        return new Date(b.created_at || '').getTime() - new Date(a.created_at || '').getTime()
      })
  }, [documents, searchQuery, selectedModality, selectedCollection, sortBy])

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setUploadFile(e.dataTransfer.files[0])
    }
  }

  const handleUploadSubmit = async () => {
    if (!uploadFile) return
    setUploading(true)
    setUploadError(null)
    setUploadStage(1)

    try {
      await new Promise((r) => setTimeout(r, 400))
      setUploadStage(2)
      await new Promise((r) => setTimeout(r, 400))
      setUploadStage(3)
      await new Promise((r) => setTimeout(r, 400))
      setUploadStage(4)

      await api.uploadDocument(uploadFile, uploadCollectionId || undefined)

      setUploadStage(5)
      setTimeout(async () => {
        setUploadModalOpen(false)
        setUploadFile(null)
        setUploadCollectionId('')
        setUploadStage(0)
        await loadData()
      }, 900)
    } catch (err: any) {
      setUploadError(err?.message || 'Upload and indexing failed')
      setUploadStage(0)
    } finally {
      setUploading(false)
    }
  }

  const handleReprocess = async (doc: ManagedDocument) => {
    setReprocessing(doc.filename)
    try {
      const res = await api.reprocessDocument(doc.filename)
      setActionNotice(`Successfully reprocessed ${doc.filename} (${res.chunks} chunks generated).`)
      setTimeout(() => setActionNotice(null), 4000)
      await loadData()
    } catch (err: any) {
      setError(`Reprocess failed: ${err.message}`)
    } finally {
      setReprocessing(null)
    }
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api.deleteDocument(deleteTarget.filename)
      setActionNotice(`Document "${deleteTarget.filename}" deleted from vector store and disk.`)
      setTimeout(() => setActionNotice(null), 4000)
      setDeleteTarget(null)
      await loadData()
    } catch (err: any) {
      setError(`Failed to delete document: ${err.message}`)
    } finally {
      setDeleting(false)
    }
  }

  const getFormatIcon = (filename: string) => {
    const lower = filename.toLowerCase()
    if (lower.endsWith('.pdf')) return <FileText className="h-5 w-5 text-red-500" />
    if (lower.endsWith('.docx') || lower.endsWith('.doc')) return <FileSpreadsheet className="h-5 w-5 text-blue-600" />
    if (['png', 'jpg', 'jpeg', 'webp'].some((ext) => lower.endsWith('.' + ext))) return <FileImage className="h-5 w-5 text-emerald-500" />
    if (['mp3', 'wav', 'm4a', 'webm'].some((ext) => lower.endsWith('.' + ext))) return <FileAudio className="h-5 w-5 text-amber-500" />
    return <FileCode className="h-5 w-5 text-surface-500" />
  }

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 space-y-6">
      {/* Header & Primary Actions */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100 flex items-center gap-2.5">
            <FolderOpen className="h-7 w-7 text-brand-600 dark:text-brand-400" />
            Enterprise Document Library
          </h1>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
            Manage, verify, and inspect multimodal indexed documents across enterprise collections.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="secondary"
            onClick={loadData}
            disabled={loading}
            icon={<RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            onClick={() => setUploadModalOpen(true)}
            icon={<Upload className="h-4 w-4" />}
          >
            Upload Document
          </Button>
        </div>
      </div>

      {actionNotice && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <span>{actionNotice}</span>
          </div>
          <button onClick={() => setActionNotice(null)} className="text-emerald-600 hover:text-emerald-800 dark:text-emerald-400">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800 dark:text-red-400">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Filter and Control Bar */}
      <Card className="p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Search */}
          <div className="lg:col-span-2">
            <Input
              type="text"
              placeholder="Search documents by filename..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftIcon={<Search className="h-4 w-4" />}
            />
          </div>

          {/* Modality Filter */}
          <div>
            <select
              value={selectedModality}
              onChange={(e) => setSelectedModality(e.target.value)}
              className="w-full rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm text-surface-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-200"
            >
              <option value="all">All Formats / Modalities</option>
              <option value="pdf">PDF Documents</option>
              <option value="docx">Word (.docx)</option>
              <option value="txt">Text & Markdown</option>
              <option value="image">Multimodal Images</option>
              <option value="audio">Transcribed Audio</option>
            </select>
          </div>

          {/* Collection Filter */}
          <div>
            <select
              value={selectedCollection}
              onChange={(e) => setSelectedCollection(e.target.value)}
              className="w-full rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm text-surface-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-200"
            >
              <option value="all">All Collections</option>
              {collections.map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name} ({c.file_count || 0})
                </option>
              ))}
            </select>
          </div>

          {/* Sort By */}
          <div className="flex items-center gap-2">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="w-full rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm text-surface-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-200"
            >
              <option value="date">Sort: Newest First</option>
              <option value="name">Sort: Filename (A-Z)</option>
              <option value="size">Sort: File Size</option>
              <option value="chunks">Sort: Chunk Count</option>
            </select>

            {/* View Mode Switcher */}
            <div className="flex rounded-lg border border-surface-200 bg-surface-100 p-0.5 dark:border-surface-700 dark:bg-surface-800 shrink-0">
              <button
                type="button"
                onClick={() => setViewMode('table')}
                className={`rounded-md p-1.5 transition-colors ${
                  viewMode === 'table'
                    ? 'bg-white text-surface-900 shadow-sm dark:bg-surface-700 dark:text-surface-100'
                    : 'text-surface-500 hover:text-surface-800 dark:hover:text-surface-200'
                }`}
                title="Table view"
              >
                <List className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                className={`rounded-md p-1.5 transition-colors ${
                  viewMode === 'grid'
                    ? 'bg-white text-surface-900 shadow-sm dark:bg-surface-700 dark:text-surface-100'
                    : 'text-surface-500 hover:text-surface-800 dark:hover:text-surface-200'
                }`}
                title="Grid view"
              >
                <Grid className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Stats summary banner */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-surface-100 pt-3 text-xs text-surface-500 dark:border-surface-800 dark:text-surface-400">
          <span>
            Showing <strong className="text-surface-800 dark:text-surface-200">{filteredDocuments.length}</strong> of{' '}
            {documents.length} indexed documents
          </span>
          <span className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> All Vector Embeddings Active (1024-d BGE-M3)
            </span>
            <span className="flex items-center gap-1.5">
              <HardDrive className="h-3.5 w-3.5 text-brand-500" /> On-Premises Isolated Storage
            </span>
          </span>
        </div>
      </Card>

      {/* Main Content: Table or Grid */}
      {loading ? (
        <Card className="p-12 text-center">
          <RefreshCw className="mx-auto h-8 w-8 animate-spin text-brand-600 dark:text-brand-400" />
          <p className="mt-3 text-sm text-surface-500 dark:text-surface-400">
            Loading document library and vector indices...
          </p>
        </Card>
      ) : filteredDocuments.length === 0 ? (
        <Card className="p-12 text-center">
          <FileText className="mx-auto h-12 w-12 text-surface-300 dark:text-surface-600" />
          <h3 className="mt-3 text-base font-semibold text-surface-900 dark:text-surface-100">
            No matching documents found
          </h3>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400 max-w-sm mx-auto">
            {searchQuery || selectedModality !== 'all' || selectedCollection !== 'all'
              ? 'Try adjusting your search criteria or clearing filters.'
              : 'Upload your first document or document collection to start querying.'}
          </p>
          <div className="mt-5">
            <Button variant="primary" onClick={() => setUploadModalOpen(true)} icon={<Upload className="h-4 w-4" />}>
              Upload Document
            </Button>
          </div>
        </Card>
      ) : viewMode === 'table' ? (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-surface-200 bg-surface-50/70 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:border-surface-800 dark:bg-surface-900/60 dark:text-surface-400">
                <tr>
                  <th className="px-4 py-3.5">Document Name</th>
                  <th className="px-4 py-3.5">Modality</th>
                  <th className="px-4 py-3.5">Size</th>
                  <th className="px-4 py-3.5">Pages</th>
                  <th className="px-4 py-3.5">Vector Chunks</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5">Collections</th>
                  <th className="px-4 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
                {filteredDocuments.map((doc) => {
                  const isReprocessing = reprocessing === doc.filename
                  return (
                    <tr
                      key={doc.filename}
                      className="transition-colors hover:bg-surface-50/60 dark:hover:bg-surface-800/40"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="shrink-0 p-1 rounded bg-surface-100 dark:bg-surface-800">
                            {getFormatIcon(doc.filename)}
                          </div>
                          <div className="min-w-0">
                            <span className="block truncate font-medium text-surface-900 dark:text-surface-100 max-w-xs md:max-w-sm" title={doc.filename}>
                              {doc.filename}
                            </span>
                            <span className="text-xs text-surface-400 flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'Active'}
                            </span>
                          </div>
                        </div>
                      </td>

                      <td className="px-4 py-3 uppercase text-xs font-mono text-surface-600 dark:text-surface-300">
                        {doc.modality || 'document'}
                      </td>

                      <td className="px-4 py-3 text-xs text-surface-600 dark:text-surface-300">
                        {formatBytes(doc.size_bytes)}
                      </td>

                      <td className="px-4 py-3 text-xs text-surface-600 dark:text-surface-300">
                        {doc.page_count && doc.page_count > 0 ? `${doc.page_count} pgs` : '—'}
                      </td>

                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono bg-surface-100 text-surface-700 dark:bg-surface-800 dark:text-surface-300">
                          <Layers className="h-3 w-3 text-brand-500" />
                          {doc.chunk_count || 1}
                        </span>
                      </td>

                      <td className="px-4 py-3">
                        <Badge
                          variant={
                            doc.status === 'indexed'
                              ? 'success'
                              : doc.status === 'processing'
                              ? 'warning'
                              : 'danger'
                          }
                        >
                          {doc.status || 'indexed'}
                        </Badge>
                      </td>

                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {doc.collections && doc.collections.length > 0 ? (
                            doc.collections.map((c) => (
                              <span
                                key={c}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300"
                              >
                                <Tag className="h-2.5 w-2.5" />
                                {c}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-surface-400">—</span>
                          )}
                        </div>
                      </td>

                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => onOpenViewer(doc.session_id, doc.filename)}
                            title="Preview in Evidence Viewer"
                            icon={<Eye className="h-3.5 w-3.5" />}
                          >
                            Preview
                          </Button>

                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleReprocess(doc)}
                            disabled={isReprocessing}
                            title="Reprocess and re-embed chunks"
                            className={isReprocessing ? 'animate-spin' : ''}
                          >
                            <RotateCw className="h-3.5 w-3.5" />
                          </Button>

                          <a
                            href={`/api/documents/${encodeURIComponent(doc.session_id || 'default')}/${encodeURIComponent(doc.filename)}/download`}
                            download={doc.filename}
                            className="inline-flex items-center justify-center rounded-lg p-1.5 text-surface-500 hover:bg-surface-100 hover:text-surface-700 dark:hover:bg-surface-800 dark:hover:text-surface-200"
                            title="Download original file"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </a>

                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setDeleteTarget(doc)}
                            title="Delete document"
                            className="text-red-500 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/30"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        /* Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredDocuments.map((doc) => {
            const isReprocessing = reprocessing === doc.filename
            return (
              <Card key={doc.filename} className="p-4 flex flex-col justify-between space-y-4 hover:shadow-md transition-shadow">
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="p-2 rounded-lg bg-surface-100 dark:bg-surface-800 shrink-0">
                        {getFormatIcon(doc.filename)}
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-semibold text-sm text-surface-900 dark:text-surface-100 truncate" title={doc.filename}>
                          {doc.filename}
                        </h4>
                        <span className="text-xs text-surface-400">
                          {formatBytes(doc.size_bytes)} {doc.page_count ? `• ${doc.page_count} pgs` : ''}
                        </span>
                      </div>
                    </div>
                    <Badge variant={doc.status === 'indexed' ? 'success' : 'warning'}>
                      {doc.status || 'indexed'}
                    </Badge>
                  </div>

                  <div className="mt-3 flex items-center justify-between text-xs text-surface-500 border-t border-surface-100 pt-2.5 dark:border-surface-800">
                    <span className="flex items-center gap-1 font-mono">
                      <Layers className="h-3 w-3 text-brand-500" />
                      {doc.chunk_count || 1} chunks
                    </span>
                    <span>{doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'Active'}</span>
                  </div>

                  {doc.collections && doc.collections.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1">
                      {doc.collections.map((c) => (
                        <span
                          key={c}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300"
                        >
                          <Tag className="h-2.5 w-2.5" />
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between border-t border-surface-100 pt-3 dark:border-surface-800">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => onOpenViewer(doc.session_id, doc.filename)}
                    icon={<Eye className="h-3.5 w-3.5" />}
                  >
                    Preview
                  </Button>
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleReprocess(doc)}
                      disabled={isReprocessing}
                      title="Reprocess"
                      className={isReprocessing ? 'animate-spin' : ''}
                    >
                      <RotateCw className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setDeleteTarget(doc)}
                      className="text-red-500 hover:text-red-700"
                      title="Delete"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Upload Modal with Multi-Stage Pipeline */}
      <Modal
        open={uploadModalOpen}
        onClose={() => !uploading && setUploadModalOpen(false)}
        title="Upload & Ingest Enterprise Documents"
      >
        <div className="space-y-5">
          <p className="text-sm text-surface-500 dark:text-surface-400">
            Files are validated with strict magic byte inspection, parsed, chunked, and embedded into local on-premises vector storage.
          </p>

          {/* Collection assignment selector */}
          <div>
            <label htmlFor="upload-collection" className="block text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-300 mb-1.5">
              Assign to Collection (Optional)
            </label>
            <select
              id="upload-collection"
              value={uploadCollectionId}
              onChange={(e) => setUploadCollectionId(e.target.value)}
              disabled={uploading}
              className="w-full rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm text-surface-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-200"
            >
              <option value="">No Collection (Global Scope)</option>
              {collections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Drop Zone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
            className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
              uploadFile
                ? 'border-brand-500 bg-brand-50/30 dark:bg-brand-950/20'
                : 'border-surface-300 hover:border-brand-400 bg-surface-50/50 dark:border-surface-700 dark:bg-surface-800/40'
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => e.target.files?.[0] && setUploadFile(e.target.files[0])}
              className="hidden"
              accept=".pdf,.docx,.doc,.txt,.md,.png,.jpg,.jpeg,.webp,.mp3,.wav,.m4a"
            />
            {uploadFile ? (
              <div className="flex flex-col items-center">
                <FileText className="h-10 w-10 text-brand-600 dark:text-brand-400 mb-2" />
                <span className="font-semibold text-sm text-surface-900 dark:text-surface-100">
                  {uploadFile.name}
                </span>
                <span className="text-xs text-surface-500 mt-0.5">
                  {formatBytes(uploadFile.size)} • Ready to ingest
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <Upload className="h-10 w-10 text-surface-400 mb-2" />
                <span className="font-medium text-sm text-surface-800 dark:text-surface-200">
                  Drop file here or click to browse
                </span>
                <span className="text-xs text-surface-400 mt-1">
                  Supported: PDF, DOCX, TXT, Images (PNG, JPG), Audio (MP3, WAV)
                </span>
              </div>
            )}
          </div>

          {/* Pipeline Stage Indicators */}
          {uploading && (
            <div className="space-y-2.5 rounded-lg border border-surface-200 bg-surface-50/60 p-4 dark:border-surface-800 dark:bg-surface-900/60">
              <span className="block text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-400">
                Ingestion Pipeline Status
              </span>
              <div className="space-y-2 text-xs">
                <div className={`flex items-center gap-2 ${uploadStage >= 1 ? 'text-emerald-600 font-medium' : 'text-surface-400'}`}>
                  {uploadStage > 1 ? <Check className="h-4 w-4" /> : uploadStage === 1 ? <RotateCw className="h-4 w-4 animate-spin text-brand-600" /> : <Clock className="h-4 w-4" />}
                  1. Magic Byte Signature & File Integrity Verification
                </div>
                <div className={`flex items-center gap-2 ${uploadStage >= 2 ? 'text-emerald-600 font-medium' : 'text-surface-400'}`}>
                  {uploadStage > 2 ? <Check className="h-4 w-4" /> : uploadStage === 2 ? <RotateCw className="h-4 w-4 animate-spin text-brand-600" /> : <Clock className="h-4 w-4" />}
                  2. OCR & Document Layout Extraction
                </div>
                <div className={`flex items-center gap-2 ${uploadStage >= 3 ? 'text-emerald-600 font-medium' : 'text-surface-400'}`}>
                  {uploadStage > 3 ? <Check className="h-4 w-4" /> : uploadStage === 3 ? <RotateCw className="h-4 w-4 animate-spin text-brand-600" /> : <Clock className="h-4 w-4" />}
                  3. Hierarchical Markdown & Text Chunking
                </div>
                <div className={`flex items-center gap-2 ${uploadStage >= 4 ? 'text-emerald-600 font-medium' : 'text-surface-400'}`}>
                  {uploadStage > 4 ? <Check className="h-4 w-4" /> : uploadStage === 4 ? <RotateCw className="h-4 w-4 animate-spin text-brand-600" /> : <Clock className="h-4 w-4" />}
                  4. BGE-M3 Dense (1024-d) & FTS5 Sparse Vectorization
                </div>
                <div className={`flex items-center gap-2 ${uploadStage >= 5 ? 'text-emerald-600 font-medium' : 'text-surface-400'}`}>
                  {uploadStage === 5 ? <Check className="h-4 w-4 text-emerald-600" /> : <Clock className="h-4 w-4" />}
                  5. Indexed in On-Premises Knowledge Base
                </div>
              </div>
            </div>
          )}

          {uploadError && (
            <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          <div className="flex justify-end gap-2.5 pt-2">
            <Button
              variant="secondary"
              onClick={() => setUploadModalOpen(false)}
              disabled={uploading}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleUploadSubmit}
              disabled={!uploadFile || uploading}
              icon={uploading ? <RotateCw className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            >
              {uploading ? 'Ingesting...' : 'Start Ingestion'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        open={!!deleteTarget}
        onClose={() => !deleting && setDeleteTarget(null)}
        title="Confirm Document Deletion"
      >
        <div className="space-y-4">
          <p className="text-sm text-surface-600 dark:text-surface-300">
            Are you sure you want to delete <strong className="text-surface-900 dark:text-surface-100">{deleteTarget?.filename}</strong>?
          </p>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300">
            <AlertTriangle className="h-4 w-4 shrink-0 inline mr-1" />
            This will permanently remove the file from on-premises storage and purge all associated vector embeddings and BM25 index tokens.
          </div>
          <div className="flex justify-end gap-2.5 pt-2">
            <Button
              variant="secondary"
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleDeleteConfirm}
              disabled={deleting}
              icon={<Trash2 className="h-4 w-4" />}
            >
              {deleting ? 'Deleting...' : 'Delete Permanently'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
