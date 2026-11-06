import React, { useState, useEffect } from 'react'
import {
  Layers,
  Plus,
  Search,
  RefreshCw,
  FolderOpen,
  FileText,
  Trash2,
  Edit2,
  MessageSquare,
  Users,
  Lock,
  Calendar,
  CheckCircle2,
  AlertCircle,
  X,
  ExternalLink,
  PlusCircle,
} from 'lucide-react'
import * as api from '../api'
import type { ManagedCollection, ManagedDocument } from '../types'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'
import { Input } from './ui/Input'
import { Modal } from './ui/Modal'

interface CollectionManagementProps {
  onChatWithCollection: (collection: ManagedCollection) => void
  onOpenViewer: (sessionId: string, filename: string) => void
}

export const CollectionManagement: React.FC<CollectionManagementProps> = ({
  onChatWithCollection,
  onOpenViewer,
}) => {
  const [collections, setCollections] = useState<ManagedCollection[]>([])
  const [allDocs, setAllDocs] = useState<ManagedDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Create Collection Modal
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newIsShared, setNewIsShared] = useState(true)
  const [creating, setCreating] = useState(false)

  // Edit Collection Modal
  const [editingCollection, setEditingCollection] = useState<ManagedCollection | null>(null)
  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [updating, setUpdating] = useState(false)

  // Delete Collection Confirm
  const [deletingCollection, setDeletingCollection] = useState<ManagedCollection | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Active Selected Collection for Detail Drawer
  const [selectedCol, setSelectedCol] = useState<ManagedCollection | null>(null)
  const [addDocModalOpen, setAddDocModalOpen] = useState(false)
  const [selectedDocsToAdd, setSelectedDocsToAdd] = useState<string[]>([])
  const [assigning, setAssigning] = useState(false)

  const [notice, setNotice] = useState<string | null>(null)

  const loadCollections = async () => {
    setLoading(true)
    setError(null)
    try {
      const [colRes, docsRes] = await Promise.all([
        api.listCollections(),
        api.listDocuments(),
      ])
      setCollections(colRes.collections || [])
      setAllDocs(docsRes.documents || [])

      if (selectedCol) {
        const refreshed = colRes.collections.find((c) => c.id === selectedCol.id)
        if (refreshed) setSelectedCol(refreshed)
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load collections')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCollections()
  }, [])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      const col = await api.createCollection({
        name: newName.trim(),
        description: newDesc.trim(),
        is_shared: newIsShared,
      })
      setNotice(`Collection "${col.name}" created successfully.`)
      setTimeout(() => setNotice(null), 4000)
      setCreateModalOpen(false)
      setNewName('')
      setNewDesc('')
      await loadCollections()
    } catch (err: any) {
      setError(`Failed to create collection: ${err.message}`)
    } finally {
      setCreating(false)
    }
  }

  const handleUpdate = async () => {
    if (!editingCollection || !editName.trim()) return
    setUpdating(true)
    try {
      await api.updateCollection(editingCollection.id, {
        name: editName.trim(),
        description: editDesc.trim(),
      })
      setNotice(`Collection updated.`)
      setTimeout(() => setNotice(null), 4000)
      setEditingCollection(null)
      await loadCollections()
    } catch (err: any) {
      setError(`Failed to update collection: ${err.message}`)
    } finally {
      setUpdating(false)
    }
  }

  const handleDelete = async () => {
    if (!deletingCollection) return
    setDeleting(true)
    try {
      await api.deleteCollection(deletingCollection.id)
      setNotice(`Collection "${deletingCollection.name}" deleted.`)
      setTimeout(() => setNotice(null), 4000)
      if (selectedCol?.id === deletingCollection.id) {
        setSelectedCol(null)
      }
      setDeletingCollection(null)
      await loadCollections()
    } catch (err: any) {
      setError(`Failed to delete collection: ${err.message}`)
    } finally {
      setDeleting(false)
    }
  }

  const handleAssignDocuments = async () => {
    if (!selectedCol || selectedDocsToAdd.length === 0) return
    setAssigning(true)
    try {
      const updated = await api.addDocumentsToCollection(selectedCol.id, selectedDocsToAdd)
      setSelectedCol(updated)
      setNotice(`Added ${selectedDocsToAdd.length} document(s) to "${selectedCol.name}".`)
      setTimeout(() => setNotice(null), 4000)
      setAddDocModalOpen(false)
      setSelectedDocsToAdd([])
      await loadCollections()
    } catch (err: any) {
      setError(`Failed to add documents: ${err.message}`)
    } finally {
      setAssigning(false)
    }
  }

  const handleRemoveDoc = async (filename: string) => {
    if (!selectedCol) return
    try {
      const updated = await api.removeDocumentFromCollection(selectedCol.id, filename)
      setSelectedCol(updated)
      setNotice(`Removed ${filename} from "${selectedCol.name}".`)
      setTimeout(() => setNotice(null), 4000)
      await loadCollections()
    } catch (err: any) {
      setError(`Failed to remove document: ${err.message}`)
    }
  }

  const filteredCollections = collections.filter((c) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase().trim()
    return c.name.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q)
  })

  const availableDocsToAdd = allDocs.filter(
    (d) => !selectedCol?.files?.includes(d.filename)
  )

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100 flex items-center gap-2.5">
            <Layers className="h-7 w-7 text-brand-600 dark:text-brand-400" />
            Document Collections & Isolation
          </h1>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
            Group documents into strict retrieval boundary collections for legal, audit, and department silos.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="secondary"
            onClick={loadCollections}
            disabled={loading}
            icon={<RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            onClick={() => setCreateModalOpen(true)}
            icon={<Plus className="h-4 w-4" />}
          >
            New Collection
          </Button>
        </div>
      </div>

      {notice && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <span>{notice}</span>
          </div>
          <button onClick={() => setNotice(null)} className="text-emerald-600 hover:text-emerald-800 dark:text-emerald-400">
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

      {/* Search & Stats Bar */}
      <Card className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="w-full sm:max-w-md">
          <Input
            type="text"
            placeholder="Search collections..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search className="h-4 w-4" />}
          />
        </div>
        <div className="text-xs text-surface-500 dark:text-surface-400">
          Total Collections: <strong>{collections.length}</strong> | Cross-tenant isolation active
        </div>
      </Card>

      {/* Grid of Collection Cards */}
      {loading ? (
        <Card className="p-12 text-center">
          <RefreshCw className="mx-auto h-8 w-8 animate-spin text-brand-600 dark:text-brand-400" />
          <p className="mt-3 text-sm text-surface-500 dark:text-surface-400">
            Loading collections and tenant scopes...
          </p>
        </Card>
      ) : filteredCollections.length === 0 ? (
        <Card className="p-12 text-center">
          <Layers className="mx-auto h-12 w-12 text-surface-300 dark:text-surface-600" />
          <h3 className="mt-3 text-base font-semibold text-surface-900 dark:text-surface-100">
            No collections found
          </h3>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400 max-w-sm mx-auto">
            {searchQuery
              ? 'No collections matched your search term.'
              : 'Create a collection to organize documents into dedicated contextual scopes.'}
          </p>
          <div className="mt-5">
            <Button variant="primary" onClick={() => setCreateModalOpen(true)} icon={<Plus className="h-4 w-4" />}>
              Create Collection
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredCollections.map((col) => {
            const isSelected = selectedCol?.id === col.id
            return (
              <Card
                key={col.id}
                className={`p-5 flex flex-col justify-between transition-all cursor-pointer ${
                  isSelected
                    ? 'ring-2 ring-brand-500 shadow-md bg-brand-50/10'
                    : 'hover:border-surface-300 dark:hover:border-surface-700 hover:shadow-sm'
                }`}
                onClick={() => setSelectedCol(col)}
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300">
                        <FolderOpen className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-base text-surface-900 dark:text-surface-100">
                          {col.name}
                        </h3>
                        <span className="text-xs text-surface-400 flex items-center gap-1 mt-0.5">
                          <Calendar className="h-3 w-3" />
                          {col.created_at ? new Date(col.created_at).toLocaleDateString() : 'Active'}
                        </span>
                      </div>
                    </div>

                    <Badge variant={col.is_shared ? 'neutral' : 'warning'}>
                      {col.is_shared ? (
                        <span className="flex items-center gap-1">
                          <Users className="h-3 w-3" /> Shared
                        </span>
                      ) : (
                        <span className="flex items-center gap-1">
                          <Lock className="h-3 w-3" /> Private
                        </span>
                      )}
                    </Badge>
                  </div>

                  <p className="mt-3 text-xs text-surface-600 dark:text-surface-300 line-clamp-2 min-h-[32px]">
                    {col.description || 'No description provided.'}
                  </p>

                  <div className="mt-4 flex items-center justify-between text-xs text-surface-500 border-t border-surface-100 pt-3 dark:border-surface-800">
                    <span className="font-medium text-surface-800 dark:text-surface-200 flex items-center gap-1.5">
                      <FileText className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
                      {col.files ? col.files.length : col.file_count || 0} Documents Assigned
                    </span>
                    <span className="text-[11px] font-mono text-surface-400">
                      org: {col.org_id || 'default'}
                    </span>
                  </div>
                </div>

                <div className="mt-5 flex items-center justify-between border-t border-surface-100 pt-3 dark:border-surface-800" onClick={(e) => e.stopPropagation()}>
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => onChatWithCollection(col)}
                    icon={<MessageSquare className="h-4 w-4" />}
                  >
                    Chat with Collection
                  </Button>

                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setEditingCollection(col)
                        setEditName(col.name)
                        setEditDesc(col.description || '')
                      }}
                      title="Edit Collection"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </Button>

                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setDeletingCollection(col)}
                      className="text-red-500 hover:text-red-700"
                      title="Delete Collection"
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

      {/* Selected Collection Detail Drawer / Panel */}
      {selectedCol && (
        <Card className="p-6 border-brand-200 dark:border-brand-900/60 bg-surface-50/50 dark:bg-surface-900/40 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-surface-200 pb-4 dark:border-surface-800">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase font-semibold text-brand-600 dark:text-brand-400 tracking-wider">
                  Active Collection Scope
                </span>
                <Badge variant="neutral">Strict Scope Enforced</Badge>
              </div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100 mt-1">
                {selectedCol.name}
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">
                {selectedCol.description || 'Dedicated document silo'}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setAddDocModalOpen(true)}
                icon={<PlusCircle className="h-4 w-4" />}
              >
                Assign Documents
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => onChatWithCollection(selectedCol)}
                icon={<MessageSquare className="h-4 w-4" />}
              >
                Start Scoped Chat
              </Button>
              <button
                onClick={() => setSelectedCol(null)}
                className="p-1.5 text-surface-400 hover:text-surface-600 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-800"
                title="Close drawer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-400 mb-3">
              Assigned Documents ({selectedCol.files?.length || 0})
            </h4>

            {!selectedCol.files || selectedCol.files.length === 0 ? (
              <div className="text-center py-8 rounded-lg border border-dashed border-surface-200 dark:border-surface-800">
                <FileText className="mx-auto h-8 w-8 text-surface-300 dark:text-surface-600" />
                <p className="mt-2 text-sm text-surface-500 dark:text-surface-400">
                  No documents currently assigned to this collection.
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-3"
                  onClick={() => setAddDocModalOpen(true)}
                  icon={<Plus className="h-4 w-4" />}
                >
                  Add Document
                </Button>
              </div>
            ) : (
              <div className="divide-y divide-surface-200 dark:divide-surface-800 rounded-lg border border-surface-200 bg-white dark:border-surface-800 dark:bg-surface-900">
                {selectedCol.files.map((fname) => (
                  <div
                    key={fname}
                    className="flex items-center justify-between p-3 transition-colors hover:bg-surface-50 dark:hover:bg-surface-800/50"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <FileText className="h-4 w-4 text-brand-600 dark:text-brand-400 shrink-0" />
                      <span className="font-medium text-sm text-surface-800 dark:text-surface-200 truncate">
                        {fname}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onOpenViewer('default', fname)}
                        icon={<ExternalLink className="h-3.5 w-3.5" />}
                        title="View document"
                      >
                        Inspect
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRemoveDoc(fname)}
                        className="text-red-500 hover:text-red-700"
                        title="Remove from collection"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Create Modal */}
      <Modal
        open={createModalOpen}
        onClose={() => !creating && setCreateModalOpen(false)}
        title="Create New Collection"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-300 mb-1.5">
              Collection Name *
            </label>
            <Input
              placeholder="e.g., Legal & Compliance 2025"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              disabled={creating}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-300 mb-1.5">
              Description (Optional)
            </label>
            <textarea
              placeholder="Brief description of the collection scope..."
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              disabled={creating}
              rows={3}
              className="w-full rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm text-surface-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-200"
            />
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="shared-check"
              checked={newIsShared}
              onChange={(e) => setNewIsShared(e.target.checked)}
              disabled={creating}
              className="rounded border-surface-300 text-brand-600 focus:ring-brand-500"
            />
            <label htmlFor="shared-check" className="text-sm text-surface-700 dark:text-surface-300">
              Share across organization members (RBAC scoped)
            </label>
          </div>

          <div className="flex justify-end gap-2.5 pt-3">
            <Button
              variant="secondary"
              onClick={() => setCreateModalOpen(false)}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleCreate}
              disabled={!newName.trim() || creating}
            >
              {creating ? 'Creating...' : 'Create Collection'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal
        open={!!editingCollection}
        onClose={() => !updating && setEditingCollection(null)}
        title="Edit Collection"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-300 mb-1.5">
              Collection Name *
            </label>
            <Input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              disabled={updating}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-300 mb-1.5">
              Description
            </label>
            <textarea
              value={editDesc}
              onChange={(e) => setEditDesc(e.target.value)}
              disabled={updating}
              rows={3}
              className="w-full rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm text-surface-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-200"
            />
          </div>

          <div className="flex justify-end gap-2.5 pt-3">
            <Button
              variant="secondary"
              onClick={() => setEditingCollection(null)}
              disabled={updating}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleUpdate}
              disabled={!editName.trim() || updating}
            >
              {updating ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Add Documents to Collection Modal */}
      <Modal
        open={addDocModalOpen}
        onClose={() => !assigning && setAddDocModalOpen(false)}
        title={`Assign Documents to "${selectedCol?.name}"`}
      >
        <div className="space-y-4">
          <p className="text-xs text-surface-500">
            Select files to assign. Only queries scoped to this collection will retrieve evidence from these documents.
          </p>

          <div className="max-h-60 overflow-y-auto space-y-1.5 border border-surface-200 rounded-lg p-2 dark:border-surface-800">
            {availableDocsToAdd.length === 0 ? (
              <p className="text-xs text-center py-4 text-surface-400">
                All existing library documents are already assigned.
              </p>
            ) : (
              availableDocsToAdd.map((doc) => {
                const checked = selectedDocsToAdd.includes(doc.filename)
                return (
                  <label
                    key={doc.filename}
                    className={`flex items-center gap-2.5 p-2 rounded cursor-pointer transition-colors ${
                      checked
                        ? 'bg-brand-50 text-brand-900 dark:bg-brand-950/60 dark:text-brand-200'
                        : 'hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-700 dark:text-surface-300'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        setSelectedDocsToAdd((prev) =>
                          checked ? prev.filter((f) => f !== doc.filename) : [...prev, doc.filename]
                        )
                      }}
                      className="rounded border-surface-300 text-brand-600"
                    />
                    <FileText className="h-4 w-4 shrink-0 text-surface-500" />
                    <span className="text-xs truncate">{doc.filename}</span>
                  </label>
                )
              })
            )}
          </div>

          <div className="flex justify-end gap-2.5 pt-2">
            <Button
              variant="secondary"
              onClick={() => setAddDocModalOpen(false)}
              disabled={assigning}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleAssignDocuments}
              disabled={selectedDocsToAdd.length === 0 || assigning}
            >
              {assigning ? 'Assigning...' : `Add Selected (${selectedDocsToAdd.length})`}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Collection Modal */}
      <Modal
        open={!!deletingCollection}
        onClose={() => !deleting && setDeletingCollection(null)}
        title="Delete Collection"
      >
        <div className="space-y-4">
          <p className="text-sm text-surface-600 dark:text-surface-300">
            Are you sure you want to delete the collection{' '}
            <strong className="text-surface-900 dark:text-surface-100">{deletingCollection?.name}</strong>?
          </p>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300">
            Documents assigned to this collection will NOT be deleted; they will remain available in the general library.
          </div>
          <div className="flex justify-end gap-2.5 pt-2">
            <Button
              variant="secondary"
              onClick={() => setDeletingCollection(null)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? 'Deleting...' : 'Delete Collection'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
