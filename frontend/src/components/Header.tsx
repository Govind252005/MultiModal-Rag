import {
  Menu,
  Cpu,
  Zap,
  Database,
  RefreshCw,
  Library,
  Sun,
  Moon,
} from "lucide-react";
import type { HealthResponse, ActiveProviderResponse } from "../types";

export default function Header({
  healthData,
  activeProvider,
  loading,
  onRefresh,
  onOpenLibrary,
  onOpenSidebar,
  onNavigate,
  theme,
  onToggleTheme,
  itemCount,
}: {
  healthData: HealthResponse | null;
  activeProvider?: ActiveProviderResponse | null;
  loading: boolean;
  onRefresh: () => void;
  onOpenLibrary: () => void;
  onOpenSidebar: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
  user?: any;
  onRequestLogout?: () => void;
  onNavigate?: (view: 'landing' | 'dashboard') => void;
  itemCount?: number;
}) {
  return (
    <header className="flex items-center justify-between gap-2 border-b border-surface-200 bg-white px-3 py-2.5 shadow-subtle dark:border-surface-800 dark:bg-surface-900 sm:px-5">
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onOpenSidebar}
          className="rounded-lg p-2 text-surface-400 transition hover:bg-surface-100 dark:hover:bg-surface-800 lg:hidden cursor-pointer"
          title="Open chats drawer"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div
          className="min-w-0 cursor-pointer group flex items-center gap-2.5"
          onClick={() => onNavigate?.('landing')}
          title="Visit Product Overview"
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-surface-900 text-surface-50 dark:bg-surface-100 dark:text-surface-950 font-mono font-bold text-xs shadow-2xs">
            M
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="truncate text-xs font-semibold leading-tight text-surface-900 dark:text-surface-100 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors uppercase tracking-wider font-mono">
                Multimodal RAG V2
              </h1>
              <span className="hidden sm:inline-block rounded bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 text-[10px] font-mono text-emerald-600 dark:text-emerald-400 border border-surface-200 dark:border-surface-700">
                {activeProvider?.mode === "cloud" ? "CLOUD HYBRID" : "LOCAL MODE"}
              </span>
            </div>
            <p className="hidden truncate text-[11px] text-surface-400 sm:block">
              Provable document reasoning across text, images, and audio
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Telemetry pill bar */}
        {healthData ? (
          <div className="hidden items-center gap-2.5 rounded-lg border border-surface-200 bg-surface-50 px-2.5 py-1 text-xs font-mono dark:border-surface-800 dark:bg-surface-850 xl:flex">
            <span className="flex items-center gap-1.5 text-surface-600 dark:text-surface-300">
              <Cpu className="h-3.5 w-3.5 text-surface-400" />
              <span className="font-semibold uppercase">{healthData.device}</span>
            </span>

            <span className="h-3.5 w-px bg-surface-200 dark:bg-surface-700" />

            <span className="flex items-center gap-1.5 text-surface-600 dark:text-surface-300">
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  activeProvider?.mode === "cloud"
                    ? "bg-sky-500"
                    : healthData.llm_available
                    ? "bg-emerald-500 animate-pulse"
                    : "bg-rose-500"
                }`}
              />
              <Zap className="h-3.5 w-3.5 text-surface-400" />
              <span>
                {activeProvider?.mode === "cloud"
                  ? `${activeProvider.provider.toUpperCase()} : ${activeProvider.model}`
                  : healthData.llm_available
                  ? `Ollama : ${activeProvider?.model || healthData.llm_model}`
                  : "LLM Offline"}
              </span>
            </span>

            <span className="h-3.5 w-px bg-surface-200 dark:bg-surface-700" />

            <span className="flex items-center gap-1.5 text-surface-600 dark:text-surface-300">
              <Database className="h-3.5 w-3.5 text-surface-400" />
              <span className="tabular-nums">
                {itemCount !== undefined ? itemCount : (healthData.index.text_items + healthData.index.image_items)} items indexed
              </span>
            </span>
          </div>
        ) : (
          <span className="hidden rounded-lg border border-surface-200 bg-surface-50 px-2.5 py-1 text-xs font-mono text-surface-400 dark:border-surface-800 dark:bg-surface-850 xl:block">
            {loading ? "Connecting to host…" : "Host offline"}
          </span>
        )}

        <button
          onClick={onRefresh}
          className="rounded-lg p-2 text-surface-400 transition hover:bg-surface-100 hover:text-surface-700 dark:hover:bg-surface-800 dark:hover:text-surface-200 cursor-pointer"
          title="Refresh system telemetry"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>

        {onToggleTheme && (
          <button
            type="button"
            onClick={onToggleTheme}
            className="rounded-lg p-2 text-surface-500 hover:bg-surface-100 hover:text-surface-800 dark:text-surface-400 dark:hover:bg-surface-800 dark:hover:text-surface-100 transition-colors cursor-pointer"
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? (
              <Sun className="h-4 w-4 text-surface-400 hover:text-surface-100" />
            ) : (
              <Moon className="h-4 w-4 text-surface-600 hover:text-surface-900" />
            )}
          </button>
        )}

        <button
          onClick={onOpenLibrary}
          className="flex items-center gap-2 rounded-lg border border-surface-800 bg-surface-900 px-3 py-1.5 text-xs font-medium text-white shadow-subtle transition hover:bg-surface-800 dark:border-surface-200 dark:bg-surface-100 dark:text-surface-950 dark:hover:bg-white cursor-pointer"
          title="Manage session sources and files"
        >
          <Library className="h-3.5 w-3.5" />
          <span className="font-mono text-xs">Library</span>
        </button>
      </div>
    </header>
  );
}
