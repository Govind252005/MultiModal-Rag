import React from 'react'
import {
  LayoutDashboard,
  MessageSquareText,
  FolderKanban,
  Layers,
  Search,
  ShieldCheck,
  Cpu,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Menu,
  Server,
  Cloud,
  Sparkles,
} from 'lucide-react'
import type { AppView, AuthUser, ActiveProviderResponse, HealthResponse } from '../../types'

export interface AppShellProps {
  currentView: AppView
  onNavigate: (view: AppView) => void
  user: AuthUser
  onLogout: () => void
  activeProvider: ActiveProviderResponse | null
  health: HealthResponse | null
  theme: 'light' | 'dark'
  onToggleTheme: () => void
  children: React.ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({
  currentView,
  onNavigate,
  user,
  onLogout,
  activeProvider,
  health,
  theme: _theme,
  onToggleTheme: _onToggleTheme,
  children,
}) => {
  const [collapsed, setCollapsed] = React.useState(false)
  const [mobileOpen, setMobileOpen] = React.useState(false)

  const isAdmin = user.role === 'admin' || user.role === 'super_admin'
  const isLocal = activeProvider?.mode === 'local'

  const navItems = [
    { view: 'dashboard' as AppView, label: 'Dashboard', icon: LayoutDashboard, section: 'Workspace' },
    { view: 'chat' as AppView, label: 'AI Chat', icon: MessageSquareText, section: 'Workspace' },
    { view: 'documents' as AppView, label: 'Documents', icon: FolderKanban, section: 'Workspace' },
    { view: 'collections' as AppView, label: 'Collections', icon: Layers, section: 'Workspace' },
    { view: 'search' as AppView, label: 'Search', icon: Search, section: 'Workspace' },
    { view: 'settings' as AppView, label: 'Models & Settings', icon: Cpu, section: 'Preferences' },
    { view: 'landing' as AppView, label: 'Platform Tour', icon: Sparkles, section: 'Preferences' },
  ]

  if (isAdmin) {
    navItems.push(
      { view: 'admin' as AppView, label: 'Administration', icon: ShieldCheck, section: 'Admin' }
    )
  }

  const sections = ['Workspace', 'Preferences', ...(isAdmin ? ['Admin'] : [])]

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-100">
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-surface-950/60 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar (Enterprise Left Rail) */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col border-r border-surface-200 bg-white transition-all duration-200 dark:border-surface-800 dark:bg-surface-900 lg:static lg:z-auto ${
          collapsed ? 'w-18' : 'w-64'
        } ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center justify-between border-b border-surface-200 px-4 dark:border-surface-800">
          <div
            onClick={() => onNavigate('landing')}
            className="flex items-center gap-2.5 overflow-hidden cursor-pointer group"
            title="View Product Overview / Landing Page"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white font-bold text-base shadow-sm group-hover:scale-105 transition-transform">
              M
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <span className="block truncate font-semibold text-sm tracking-tight text-surface-900 dark:text-surface-100 group-hover:text-brand-600 transition-colors">
                  Multimodal RAG
                </span>
                <span className="block truncate text-[11px] text-surface-400 font-mono">
                  Enterprise v2.0
                </span>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className="hidden lg:flex rounded-lg p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600 dark:hover:bg-surface-800 dark:hover:text-surface-200"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        {/* Navigation Items */}
        <div className="scroll-thin flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {sections.map((sec) => (
            <div key={sec} className="space-y-1">
              {!collapsed && (
                <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">
                  {sec}
                </p>
              )}
              {navItems
                .filter((item) => item.section === sec)
                .map((item) => {
                  const Icon = item.icon
                  const active = currentView === item.view
                  return (
                    <button
                      key={item.view}
                      onClick={() => {
                        onNavigate(item.view)
                        setMobileOpen(false)
                      }}
                      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                        active
                          ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300'
                          : 'text-surface-600 hover:bg-surface-100 hover:text-surface-900 dark:text-surface-400 dark:hover:bg-surface-800 dark:hover:text-surface-100'
                      }`}
                      title={collapsed ? item.label : undefined}
                    >
                      <Icon className={`h-4 w-4 shrink-0 ${active ? 'text-brand-600 dark:text-brand-400' : ''}`} />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </button>
                  )
                })}
            </div>
          ))}
        </div>

        {/* Genuine Status Pill: Local vs Cloud Processing Indicator */}
        <div className="border-t border-surface-200 p-3 dark:border-surface-800">
          {!collapsed ? (
            <div
              className={`rounded-xl p-3 border text-xs ${
                isLocal
                  ? 'border-emerald-200 bg-emerald-50/70 text-emerald-900 dark:border-emerald-800/80 dark:bg-emerald-950/30 dark:text-emerald-200'
                  : 'border-brand-200 bg-brand-50/70 text-brand-900 dark:border-brand-800/80 dark:bg-brand-950/30 dark:text-brand-200'
              }`}
            >
              <div className="flex items-center gap-2 font-semibold">
                {isLocal ? (
                  <>
                    <Server className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    <span>Local Processing Active</span>
                  </>
                ) : (
                  <>
                    <Cloud className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400 shrink-0" />
                    <span>Cloud Connected</span>
                  </>
                )}
              </div>
              <p className="mt-1 text-[11px] opacity-80 truncate">
                {isLocal
                  ? `Local Qwen (Ollama: ${activeProvider?.model || health?.llm_model || 'qwen2.5:7b-instruct'})`
                  : `${activeProvider?.provider || 'Cloud'}: ${activeProvider?.model || 'Active'}`}
              </p>
            </div>
          ) : (
            <div className="flex justify-center" title={isLocal ? 'Local Processing Active' : 'Cloud Connected'}>
              <span
                className={`h-2.5 w-2.5 rounded-full ${isLocal ? 'bg-emerald-500' : 'bg-brand-500'}`}
              />
            </div>
          )}

          {/* User Profile Card */}
          <div className="mt-3 flex items-center justify-between pt-3 border-t border-surface-100 dark:border-surface-800/80">
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-200 text-xs font-semibold uppercase text-surface-700 dark:bg-surface-800 dark:text-surface-300">
                {user.email.slice(0, 2)}
              </div>
              {!collapsed && (
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-surface-900 dark:text-surface-100">
                    {user.email}
                  </p>
                  <p className="truncate text-[10px] text-surface-400 capitalize">
                    {user.role || 'Member'}
                  </p>
                </div>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={onLogout}
                className="rounded-lg p-1.5 text-surface-400 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40 dark:hover:text-rose-400 transition-colors cursor-pointer"
                title="Sign Out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Navbar */}
        <header className="flex h-16 items-center justify-between border-b border-surface-200 bg-white px-4 dark:border-surface-800 dark:bg-surface-900">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Open navigation menu"
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-1.5 text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-surface-400 uppercase tracking-wider">
                Workspace
              </span>
              <span className="text-surface-300 dark:text-surface-700">/</span>
              <h1 className="text-sm font-semibold capitalize text-surface-800 dark:text-surface-200">
                {currentView}
              </h1>
            </div>
          </div>
        </header>

        {/* View Outlet */}
        <main className="flex-1 overflow-auto bg-surface-50 dark:bg-surface-950">
          {children}
        </main>
      </div>
    </div>
  )
}
