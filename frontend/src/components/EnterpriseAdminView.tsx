import React, { useState, useEffect } from 'react'
import {
  ShieldCheck,
  Users,
  Search,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  UserCheck,
  UserX,
  Clock,
  Filter,
  Eye,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react'
import * as api from '../api'
import type { AdminUserRecord, AuditLogRecord } from '../types'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'
import { Input } from './ui/Input'
import { Modal } from './ui/Modal'

export const EnterpriseAdminView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'users' | 'audit'>('users')
  const [users, setUsers] = useState<AdminUserRecord[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([])
  const [auditTotal, setAuditTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  // User search
  const [userSearch, setUserSearch] = useState('')

  // Audit filters & pagination
  const [auditActionFilter, setAuditActionFilter] = useState('')
  const [auditEmailFilter, setAuditEmailFilter] = useState('')
  const [auditOffset, setAuditOffset] = useState(0)
  const auditLimit = 25

  // User status toggling confirm modal
  const [statusTarget, setStatusTarget] = useState<{ user: AdminUserRecord; nextStatus: 'active' | 'disabled' } | null>(null)
  const [statusUpdating, setStatusUpdating] = useState(false)

  // Details Modal for Audit Log
  const [viewLogDetail, setViewLogDetail] = useState<AuditLogRecord | null>(null)

  const loadUsers = async () => {
    try {
      const uList = await api.adminListUsers()
      setUsers(uList || [])
    } catch (err: any) {
      setError(`Failed to load users: ${err.message}`)
    }
  }

  const loadAuditLogs = async () => {
    try {
      const res = await api.adminGetAuditLogs({
        limit: auditLimit,
        offset: auditOffset,
        action: auditActionFilter || undefined,
        user_email: auditEmailFilter || undefined,
      })
      setAuditLogs(res.logs || [])
      setAuditTotal(res.total || 0)
    } catch (err: any) {
      setError(`Failed to load audit logs: ${err.message}`)
    }
  }

  const loadAll = async () => {
    setLoading(true)
    setError(null)
    await Promise.all([loadUsers(), loadAuditLogs()])
    setLoading(false)
  }

  useEffect(() => {
    loadAll()
  }, [])

  useEffect(() => {
    if (activeTab === 'audit') {
      loadAuditLogs()
    }
  }, [auditOffset, auditActionFilter, auditEmailFilter, activeTab])

  const handleRoleChange = async (email: string, role: string) => {
    try {
      await api.adminSetRole(email, role)
      setNotice(`Updated role for ${email} to ${role.toUpperCase()}.`)
      setTimeout(() => setNotice(null), 3000)
      await loadUsers()
    } catch (err: any) {
      setError(`Failed to update role: ${err.message}`)
    }
  }

  const handleStatusConfirm = async () => {
    if (!statusTarget) return
    setStatusUpdating(true)
    try {
      await api.adminSetUserStatus(statusTarget.user.email, statusTarget.nextStatus)
      setNotice(`User ${statusTarget.user.email} is now ${statusTarget.nextStatus.toUpperCase()}.`)
      setTimeout(() => setNotice(null), 3000)
      setStatusTarget(null)
      await loadUsers()
      await loadAuditLogs()
    } catch (err: any) {
      setError(`Failed to update user status: ${err.message}`)
    } finally {
      setStatusUpdating(false)
    }
  }

  const filteredUsers = users.filter((u) => {
    if (!userSearch.trim()) return true
    const q = userSearch.toLowerCase().trim()
    return u.email.toLowerCase().includes(q) || (u.role || '').toLowerCase().includes(q)
  })

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100 flex items-center gap-2.5">
            <ShieldCheck className="h-7 w-7 text-brand-600 dark:text-brand-400" />
            Enterprise Administration
          </h1>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
            Role-based access control enforced across tenant isolation and structured security audit logging.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="secondary"
            onClick={loadAll}
            disabled={loading}
            icon={<RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {notice && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <span>{notice}</span>
          </div>
          <button onClick={() => setNotice(null)} className="text-emerald-600 hover:text-emerald-800">
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
          <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-surface-200 dark:border-surface-800 gap-6">
        <button
          onClick={() => setActiveTab('users')}
          className={`flex items-center gap-2 pb-3 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'users'
              ? 'border-brand-600 text-brand-600 dark:border-brand-400 dark:text-brand-400'
              : 'border-transparent text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
          }`}
        >
          <Users className="h-4 w-4" />
          User Management ({users.length})
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`flex items-center gap-2 pb-3 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'audit'
              ? 'border-brand-600 text-brand-600 dark:border-brand-400 dark:text-brand-400'
              : 'border-transparent text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
          }`}
        >
          <Clock className="h-4 w-4" />
          Security Audit Logs ({auditTotal})
        </button>
      </div>

      {/* TAB 1: User Management */}
      {activeTab === 'users' && (
        <div className="space-y-4">
          <Card className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="w-full sm:max-w-md">
              <Input
                type="text"
                placeholder="Search users by email or role..."
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                leftIcon={<Search className="h-4 w-4" />}
              />
            </div>
            <div className="text-xs text-surface-500">
              Active Users: <strong>{users.filter((u) => u.status !== 'disabled').length}</strong> | Disabled: <strong>{users.filter((u) => u.status === 'disabled').length}</strong>
            </div>
          </Card>

          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-surface-200 bg-surface-50/70 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:border-surface-800 dark:bg-surface-900/60 dark:text-surface-400">
                  <tr>
                    <th className="px-4 py-3.5">User Email</th>
                    <th className="px-4 py-3.5">Role</th>
                    <th className="px-4 py-3.5">Org Scope</th>
                    <th className="px-4 py-3.5">Account Status</th>
                    <th className="px-4 py-3.5">Registered</th>
                    <th className="px-4 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
                  {filteredUsers.map((u) => {
                    const isDisabled = u.status === 'disabled'
                    return (
                      <tr key={u.id} className="transition-colors hover:bg-surface-50/60 dark:hover:bg-surface-800/40">
                        <td className="px-4 py-3 font-medium text-surface-900 dark:text-surface-100">
                          {u.email}
                        </td>

                        <td className="px-4 py-3">
                          <select
                            value={u.role || 'user'}
                            onChange={(e) => handleRoleChange(u.email, e.target.value)}
                            className="rounded border border-surface-200 bg-white px-2 py-1 text-xs font-medium text-surface-800 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-200"
                          >
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                          </select>
                        </td>

                        <td className="px-4 py-3 font-mono text-xs text-surface-500">
                          {u.org_id || 'default_org'}
                        </td>

                        <td className="px-4 py-3">
                          <Badge variant={isDisabled ? 'danger' : 'success'}>
                            {isDisabled ? 'Disabled' : 'Active'}
                          </Badge>
                        </td>

                        <td className="px-4 py-3 text-xs text-surface-400">
                          {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                        </td>

                        <td className="px-4 py-3 text-right">
                          <Button
                            size="sm"
                            variant={isDisabled ? 'primary' : 'secondary'}
                            onClick={() =>
                              setStatusTarget({
                                user: u,
                                nextStatus: isDisabled ? 'active' : 'disabled',
                              })
                            }
                            icon={isDisabled ? <UserCheck className="h-4 w-4" /> : <UserX className="h-4 w-4" />}
                          >
                            {isDisabled ? 'Re-activate' : 'Deactivate'}
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 2: Audit Logs */}
      {activeTab === 'audit' && (
        <div className="space-y-4">
          <Card className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Input
              placeholder="Filter by action (e.g., query, upload)..."
              value={auditActionFilter}
              onChange={(e) => setAuditActionFilter(e.target.value)}
              leftIcon={<Search className="h-4 w-4" />}
            />

            <Input
              placeholder="Filter by user email..."
              value={auditEmailFilter}
              onChange={(e) => setAuditEmailFilter(e.target.value)}
              leftIcon={<Filter className="h-4 w-4" />}
            />

            <div className="flex items-center justify-end gap-2 text-xs text-surface-500">
              <span>
                Showing {auditLogs.length} of {auditTotal} events
              </span>
              <Button
                size="sm"
                variant="secondary"
                disabled={auditOffset === 0}
                onClick={() => setAuditOffset((prev) => Math.max(0, prev - auditLimit))}
                icon={<ChevronLeft className="h-4 w-4" />}
              >
                Prev
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={auditOffset + auditLimit >= auditTotal}
                onClick={() => setAuditOffset((prev) => prev + auditLimit)}
                icon={<ChevronRight className="h-4 w-4" />}
              >
                Next
              </Button>
            </div>
          </Card>

          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-surface-200 bg-surface-50/70 font-semibold uppercase tracking-wider text-surface-500 dark:border-surface-800 dark:bg-surface-900/60 dark:text-surface-400">
                  <tr>
                    <th className="px-3.5 py-3">Timestamp (UTC)</th>
                    <th className="px-3.5 py-3">Action</th>
                    <th className="px-3.5 py-3">User</th>
                    <th className="px-3.5 py-3">Tenant / Org</th>
                    <th className="px-3.5 py-3">IP Address</th>
                    <th className="px-3.5 py-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
                  {auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-surface-400">
                        No audit events recorded matching current criteria.
                      </td>
                    </tr>
                  ) : (
                    auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-surface-50/60 dark:hover:bg-surface-800/40">
                        <td className="px-3.5 py-2.5 font-mono text-surface-600 dark:text-surface-400">
                          {log.timestamp}
                        </td>
                        <td className="px-3.5 py-2.5 font-mono font-semibold text-brand-600 dark:text-brand-400">
                          {log.action}
                        </td>
                        <td className="px-3.5 py-2.5 text-surface-800 dark:text-surface-200">
                          {log.user_email || log.user_id || 'system'}
                        </td>
                        <td className="px-3.5 py-2.5 font-mono text-surface-500">
                          {log.org_id || 'default_org'}
                        </td>
                        <td className="px-3.5 py-2.5 font-mono text-surface-500">
                          {log.ip || '127.0.0.1'}
                        </td>
                        <td className="px-3.5 py-2.5 text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setViewLogDetail(log)}
                            icon={<Eye className="h-3.5 w-3.5" />}
                          >
                            Inspect
                          </Button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* Status Deactivate/Re-activate Modal */}
      <Modal
        open={!!statusTarget}
        onClose={() => !statusUpdating && setStatusTarget(null)}
        title={statusTarget?.nextStatus === 'disabled' ? 'Deactivate User Account' : 'Re-activate User Account'}
      >
        <div className="space-y-4">
          <p className="text-sm text-surface-600 dark:text-surface-300">
            Are you sure you want to {statusTarget?.nextStatus === 'disabled' ? 'deactivate' : 're-activate'}{' '}
            <strong className="text-surface-900 dark:text-surface-100">{statusTarget?.user.email}</strong>?
          </p>
          {statusTarget?.nextStatus === 'disabled' && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
              A deactivated user cannot authenticate, generate retrieval tokens, or query any models until re-activated by an administrator.
            </div>
          )}
          <div className="flex justify-end gap-2.5 pt-2">
            <Button
              variant="secondary"
              onClick={() => setStatusTarget(null)}
              disabled={statusUpdating}
            >
              Cancel
            </Button>
            <Button
              variant={statusTarget?.nextStatus === 'disabled' ? 'danger' : 'primary'}
              onClick={handleStatusConfirm}
              disabled={statusUpdating}
            >
              {statusUpdating ? 'Updating...' : `Confirm ${statusTarget?.nextStatus === 'disabled' ? 'Deactivation' : 'Re-activation'}`}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Detail JSON Modal */}
      <Modal
        open={!!viewLogDetail}
        onClose={() => setViewLogDetail(null)}
        title="Audit Log Event Inspection"
      >
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-surface-500">Event ID:</span>
            <span className="font-mono text-surface-700 dark:text-surface-300">{viewLogDetail?.id}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-surface-500">Action:</span>
            <span className="font-mono text-brand-600 dark:text-brand-400 font-semibold">{viewLogDetail?.action}</span>
          </div>
          <pre className="p-3 rounded-lg bg-surface-950 text-emerald-400 font-mono text-xs overflow-x-auto max-h-60">
            {JSON.stringify(viewLogDetail?.details || {}, null, 2)}
          </pre>
          <div className="flex justify-end pt-2">
            <Button variant="secondary" onClick={() => setViewLogDetail(null)}>
              Close
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
