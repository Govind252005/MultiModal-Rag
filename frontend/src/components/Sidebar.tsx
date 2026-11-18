import {
  Plus,
  MessageSquare,
  Trash2,
  X,
  PanelLeftOpen,
  PanelLeftClose,
  ChevronUp,
  ChevronDown,
  Cpu,
} from 'lucide-react'
import type { SessionSummary, ProviderName } from '../types'
import ProviderPanel from './ProviderPanel'

/**
 * Left sidebar: New chat button + saved chat history.
 * Static column on desktop; slide-over drawer on mobile (controlled by `open`).
 * Industrial precision styling.
 */
export default function Sidebar({
  sessions,
  currentId,
  onNew,
  onSelect,
  onDelete,
  open,
  onClose,
  provider,
  onSelectProvider,
  onError,
  collapsed,
  onToggleCollapse,
  modelsCollapsed,
  onToggleModels,
}: {
  sessions: SessionSummary[]
  currentId: string | null
  onNew: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  open: boolean
  onClose: () => void
  provider: ProviderName
  onSelectProvider: (p: ProviderName, model?: string) => void
  onError: (msg: string) => void
  collapsed: boolean
  onToggleCollapse: () => void
  modelsCollapsed: boolean
  onToggleModels: () => void
}) {
  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-surface-950/60 backdrop-blur-xs md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 transform flex-col border-r border-surface-200 bg-white transition-transform duration-200 dark:border-surface-800 dark:bg-surface-900 md:static md:z-auto md:translate-x-0 md:transition-[width] ${
          collapsed ? 'md:w-20' : 'md:w-72'
        } ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Brand + close (mobile) */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-surface-100 dark:border-surface-850">
          <button
            type="button"
            onClick={onToggleCollapse}
            className="flex items-center gap-2.5 rounded-lg p-0.5 text-left transition hover:bg-surface-100 dark:hover:bg-surface-800 cursor-pointer"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-surface-900 text-surface-50 dark:bg-surface-100 dark:text-surface-950 font-mono font-bold text-xs shadow-2xs">
              M
            </div>
            {!collapsed && (
              <span className="text-xs font-mono font-semibold tracking-wider uppercase text-surface-900 dark:text-surface-100">
                Multimodal RAG
              </span>
            )}
          </button>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onToggleCollapse}
              className="hidden rounded-lg p-1.5 text-surface-400 transition hover:bg-surface-100 hover:text-surface-700 dark:hover:bg-surface-800 dark:hover:text-surface-200 md:block cursor-pointer"
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 md:hidden cursor-pointer"
              title="Close drawer"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* New chat button */}
        <div className="p-3">
          <button
            type="button"
            onClick={onNew}
            className={`flex w-full items-center rounded-lg border border-surface-200 bg-surface-50 py-2 text-xs font-semibold text-surface-800 transition hover:border-surface-400 hover:bg-surface-100 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-100 dark:hover:border-surface-600 dark:hover:bg-surface-750 shadow-2xs cursor-pointer ${
              collapsed ? 'justify-center px-0' : 'gap-2 px-3'
            }`}
            title="Start new conversation"
          >
            <Plus className="h-3.5 w-3.5" />
            {!collapsed && <span>New Session</span>}
          </button>
        </div>

        {/* Chat list */}
        <div className="scroll-thin flex-1 overflow-y-auto px-2 pb-4">
          {!collapsed && (
            <p className="px-2 py-1 text-[10px] font-mono font-semibold uppercase tracking-wider text-surface-400">
              Active Sessions
            </p>
          )}

          {sessions.length === 0 ? (
            !collapsed && (
              <p className="px-2 py-3 text-xs text-surface-400">No active sessions.</p>
            )
          ) : (
            <ul className="space-y-1">
              {sessions.map((s) => (
                <li key={s.id}>
                  <div
                    className={`group flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs transition border ${
                      currentId === s.id
                        ? 'border-surface-200 bg-surface-100/90 text-surface-900 font-medium dark:border-surface-700 dark:bg-surface-800 dark:text-surface-50'
                        : 'border-transparent text-surface-600 hover:bg-surface-50 hover:text-surface-900 dark:text-surface-400 dark:hover:bg-surface-850 dark:hover:text-surface-200'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelect(s.id)}
                      className="flex min-w-0 flex-1 items-center gap-2 text-left cursor-pointer"
                      title={s.title}
                    >
                      <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-50" />
                      {!collapsed && (
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-xs">{s.title}</span>
                          <span className="block truncate text-[10px] font-mono text-surface-400">
                            {s.file_count} file(s) · {s.message_count} msg
                          </span>
                        </span>
                      )}
                    </button>

                    {!collapsed && (
                      <button
                        type="button"
                        onClick={() => onDelete(s.id)}
                        className="rounded p-1 text-surface-400 opacity-0 transition hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100 dark:hover:bg-rose-950/40 dark:hover:text-rose-300 cursor-pointer"
                        title="Delete session"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Provider downbar: collapsible independently from sidebar */}
        <div className="border-t border-surface-200 px-3 py-2 dark:border-surface-800 bg-surface-50/50 dark:bg-surface-950/50">
          <button
            type="button"
            onClick={onToggleModels}
            className={`flex w-full items-center rounded-lg text-left text-xs font-mono font-semibold uppercase tracking-wider text-surface-500 transition hover:bg-surface-100 dark:hover:bg-surface-800 cursor-pointer ${
              collapsed ? 'justify-center px-0 py-2' : 'justify-between px-1.5 py-1.5'
            }`}
            title={modelsCollapsed ? 'Expand model configuration' : 'Collapse model configuration'}
          >
            {collapsed ? (
              <Cpu className="h-4 w-4" />
            ) : (
              <>
                <span className="text-[10px]">Reasoning Model</span>
                {modelsCollapsed ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </>
            )}
          </button>

          {!modelsCollapsed && (
            <ProviderPanel
              provider={provider}
              onSelect={onSelectProvider}
              onError={onError}
              collapsed={collapsed}
              showHeading={false}
            />
          )}

          {modelsCollapsed && !collapsed && (
            <p className="px-1.5 pb-1 font-mono text-[10px] text-surface-400">
              Active: {provider}
            </p>
          )}
        </div>
      </aside>
    </>
  )
}
