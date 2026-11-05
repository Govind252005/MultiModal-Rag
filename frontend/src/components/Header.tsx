import {
  Menu,
  Cpu,
  Zap,
  Database,
  RefreshCw,
  Library,
  Sun,
  Moon,
  LogOut,
} from "lucide-react";
import type { AuthUser, HealthResponse, ActiveProviderResponse } from "../types";

export default function Header({
  healthData,
  activeProvider,
  loading,
  onRefresh,
  onOpenLibrary,
  onOpenSidebar,
  theme,
  onToggleTheme,
  user,
  onRequestLogout,
}: {
  healthData: HealthResponse | null;
  activeProvider?: ActiveProviderResponse | null;
  loading: boolean;
  onRefresh: () => void;
  onOpenLibrary: () => void;
  onOpenSidebar: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  user: AuthUser;
  onRequestLogout: () => void;
}) {

  return (
    <header className="flex items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 py-2.5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:px-5">
      <div className="flex min-w-0 items-center gap-2">
        <button
          onClick={onOpenSidebar}
          className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 dark:hover:bg-slate-800 lg:hidden"
          title="Open chats"
        >
          <Menu className="h-4 w-4" />
        </button>
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold leading-tight text-slate-900 dark:text-slate-100">
            Multimodal Offline RAG
          </h1>
          <p className="hidden truncate text-xs text-slate-500 dark:text-slate-400 sm:block">
            Ask across documents, images &amp; audio — fully offline
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        {healthData ? (
          <div className="hidden items-center gap-3 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800 xl:flex">
            <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
              <Cpu className="h-4 w-4 text-slate-400" />
              <span className="font-medium uppercase">{healthData.device}</span>
            </span>
            <span className="h-4 w-px bg-slate-200 dark:bg-slate-700" />
            <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
              <span
                className={`inline-block h-2.5 w-2.5 rounded-full ${
                  activeProvider?.mode === "cloud"
                    ? "bg-sky-500"
                    : healthData.llm_available
                    ? "bg-emerald-500"
                    : "bg-red-500"
                }`}
              />
              <Zap className="h-4 w-4 text-slate-400" />
              <span className="font-medium">
                {activeProvider?.mode === "cloud"
                  ? `${activeProvider.provider.toUpperCase()} — ${activeProvider.model}`
                  : healthData.llm_available
                  ? `Ollama — ${healthData.llm_model}`
                  : "LLM offline"}
              </span>
            </span>
            <span className="h-4 w-px bg-slate-200 dark:bg-slate-700" />
            <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
              <Database className="h-4 w-4 text-slate-400" />
              <span className="font-medium">
                {healthData.index.text_items + healthData.index.image_items}{" "}
                items
              </span>
            </span>
          </div>
        ) : (
          <span className="hidden rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-400 dark:border-slate-700 dark:bg-slate-800 xl:block">
            {loading ? "Connecting…" : "Backend offline"}
          </span>
        )}

        <button
          onClick={onRefresh}
          className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 dark:hover:bg-slate-800"
          title="Refresh status"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
        <button
          onClick={onToggleTheme}
          className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 dark:hover:bg-slate-800"
          title="Toggle light / dark"
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>

        <button
          onClick={onOpenLibrary}
          className="flex items-center gap-2 rounded-lg bg-accent-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-accent-700"
          title="Manage this chat's library"
        >
          <Library className="h-4 w-4" />
          <span className="hidden sm:inline">Library</span>
        </button>

        <span
          className="ml-1 hidden max-w-[140px] truncate text-xs text-slate-500 dark:text-slate-400 lg:block"
          title={user.email}
        >
          {user.email}
        </span>
        <button
          onClick={onRequestLogout}
          className="rounded-lg p-2 text-slate-400 transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-500/10"
          title="Log out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
