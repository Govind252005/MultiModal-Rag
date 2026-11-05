import { Plus, MessageSquare, Trash2, Boxes, X, PanelLeftOpen, PanelLeftClose, ChevronUp, ChevronDown, Cpu } from 'lucide-react'
import type { SessionSummary, ProviderName } from '../types'
import ProviderPanel from './ProviderPanel'

/**
 * Left sidebar: New chat button + saved chat history (ChatGPT-style).
 * Static column on desktop; slide-over drawer on mobile (controlled by `open`).
 * Each chat keeps its OWN library + messages, restored on click.
 */
export default function Sidebar({
  sessions, currentId, onNew, onSelect, onDelete, open, onClose,
  provider, onSelectProvider, onError, collapsed, onToggleCollapse, modelsCollapsed, onToggleModels,
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
        <div className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-sm md:hidden" onClick={onClose} />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 transform flex-col border-r border-slate-200 bg-white transition-transform duration-300 dark:border-slate-800 dark:bg-slate-900 md:static md:z-auto md:translate-x-0 md:transition-[width] ${
          collapsed ? 'md:w-20' : 'md:w-72'
        } ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand + close (mobile) */}
        <div className="flex items-center justify-between px-4 py-3">
          <button
            onClick={onToggleCollapse}
            className="flex items-center gap-2 rounded-lg p-0.5 text-left transition hover:bg-slate-100 dark:hover:bg-slate-800"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent-500 to-accent-700 text-white">
              <Boxes className="h-5 w-5" />
            </div>
            {!collapsed && <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Multimodal RAG</span>}
          </button>
          <div className="flex items-center gap-1">
            <button
              onClick={onToggleCollapse}
              className="hidden rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 md:block"
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </button>
            <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 md:hidden">
            <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* New chat */}
        <div className="px-3">
          <button
            onClick={onNew}
            className={`flex w-full items-center rounded-xl border border-slate-200 bg-slate-50 py-2.5 text-sm font-medium text-slate-700 transition hover:border-accent-300 hover:bg-accent-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-accent-500/40 dark:hover:bg-slate-800/60 ${
              collapsed ? 'justify-center px-0' : 'gap-2 px-3'
            }`}
            title="New chat"
          >
            <Plus className="h-4 w-4" /> {!collapsed && 'New chat'}
          </button>
        </div>

        {/* Chat list */}
        <div className="scroll-thin mt-3 flex-1 overflow-y-auto px-2 pb-4">
          {!collapsed && <p className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Chats</p>}
          {sessions.length === 0 ? (
            !collapsed && <p className="px-2 py-3 text-xs text-slate-400">No saved chats yet.</p>
          ) : (
            <ul className="space-y-1">
              {sessions.map((s) => (
                <li key={s.id}>
                  <div
                    className={`group flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition ${
                      currentId === s.id
                        ? 'bg-accent-50 text-accent-800 dark:bg-accent-500/15 dark:text-accent-100'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`}
                  >
                    <button onClick={() => onSelect(s.id)} className="flex min-w-0 flex-1 items-center gap-2 text-left" title={s.title}>
                      <MessageSquare className="h-4 w-4 shrink-0 opacity-60" />
                      {!collapsed && (
                        <span className="min-w-0 flex-1">
                          <span className="block truncate">{s.title}</span>
                          <span className="block truncate text-[10px] text-slate-400">
                            {s.file_count} file(s) · {s.message_count} msg
                          </span>
                        </span>
                      )}
                    </button>
                    {!collapsed && (
                      <button
                        onClick={() => onDelete(s.id)}
                        className="rounded p-1 text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 dark:hover:bg-red-500/10"
                        title="Delete chat"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Provider downbar: collapsible independently from sidebar */}
        <div className="border-t border-slate-200 px-3 py-2 dark:border-slate-800">
          <button
            onClick={onToggleModels}
            className={`flex w-full items-center rounded-lg text-left text-xs font-semibold uppercase tracking-wide text-slate-400 transition hover:bg-slate-100 dark:hover:bg-slate-800 ${
              collapsed ? 'justify-center px-0 py-2' : 'justify-between px-1 py-1.5'
            }`}
            title={modelsCollapsed ? 'Expand answer models' : 'Collapse answer models'}
          >
            {collapsed ? (
              <Cpu className="h-4 w-4" />
            ) : (
              <>
                <span>Answer model</span>
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
            <p className="px-1 pb-1 text-[11px] text-slate-400">Current: {provider}</p>
          )}
        </div>
      </aside>
    </>
  )
}
