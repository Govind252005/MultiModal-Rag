import { useState } from "react";
import type { FormEvent } from "react";
import {
  Mail,
  Lock,
  Loader2,
  LogIn,
  UserPlus,
  Eye,
  EyeOff,
  ShieldCheck,
  FileText,
  ImageIcon,
  Mic,
  Cpu,
} from "lucide-react";
import * as api from "../api";
import type { AuthUser } from "../types";

export default function Login({ onAuthed }: { onAuthed: (user: AuthUser) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setError("Please fill in all required fields.");
      return;
    }
    if (mode === "register") {
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
    }
    setBusy(true);
    try {
      const res =
        mode === "login"
          ? await api.login(cleanEmail, password)
          : await api.register(cleanEmail, password);
      api.setToken(res.token);
      onAuthed(res.user);
    } catch (err) {
      setError((err as Error).message || "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-100">
      {/* Left panel: Enterprise Blueprint & Trust */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between border-r border-surface-200 dark:border-surface-800 bg-surface-100/60 dark:bg-surface-900/60 p-12">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white font-bold text-base shadow-sm">
              M
            </div>
            <div>
              <span className="font-semibold text-base tracking-tight text-surface-900 dark:text-surface-100">
                Multimodal RAG
              </span>
              <span className="ml-2 text-xs font-mono text-surface-500">Enterprise</span>
            </div>
          </div>

          <div className="mt-16 max-w-md space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-surface-300 dark:border-surface-700 bg-surface-200/50 dark:bg-surface-800/50 px-3 py-1 text-xs font-medium text-surface-700 dark:text-surface-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              On-Premises Privacy &amp; Enterprise Cloud Hybrid
            </div>

            <h1 className="text-3xl font-bold tracking-tight text-surface-900 dark:text-surface-50 leading-tight">
              Verifiable document intelligence across documents, images, and audio.
            </h1>

            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              Every inference result carries direct citations linked to original source passages,
              bounding boxes, and exact timestamps. Zero external telemetry leaks.
            </p>

            <div className="space-y-3 pt-4">
              <div className="flex items-center gap-3 text-xs text-surface-700 dark:text-surface-300">
                <FileText className="h-4 w-4 text-brand-600 dark:text-brand-400" />
                <span>PDF, DOCX, PPTX, XLSX with layout-aware table extraction</span>
              </div>
              <div className="flex items-center gap-3 text-xs text-surface-700 dark:text-surface-300">
                <ImageIcon className="h-4 w-4 text-brand-600 dark:text-brand-400" />
                <span>Dual PP-OCRv6 + CLIP dense visual embeddings</span>
              </div>
              <div className="flex items-center gap-3 text-xs text-surface-700 dark:text-surface-300">
                <Mic className="h-4 w-4 text-brand-600 dark:text-brand-400" />
                <span>Local Whisper speech transcription with segment timestamps</span>
              </div>
              <div className="flex items-center gap-3 text-xs text-surface-700 dark:text-surface-300">
                <Cpu className="h-4 w-4 text-brand-600 dark:text-brand-400" />
                <span>Local Ollama Qwen2.5-7B or private cloud models via TLS</span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-surface-500">
          <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          <span>Tenant isolation enforced with SQLite rate-limiting &amp; audit logging.</span>
        </div>
      </div>

      {/* Right panel: Login / Register Form */}
      <div className="flex flex-1 flex-col justify-center items-center px-6 py-12 lg:px-12">
        <div className="w-full max-w-sm space-y-6">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
              {mode === "login" ? "Sign in to workspace" : "Create enterprise account"}
            </h2>
            <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">
              {mode === "login"
                ? "Enter your credentials to access your session library"
                : "Register a new workspace on this instance"}
            </p>
          </div>

          {/* Mode Switcher */}
          <div className="flex rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-100 dark:bg-surface-900 p-1 text-xs font-medium">
            <button
              type="button"
              onClick={() => { setMode("login"); setError(null); }}
              className={`flex-1 py-1.5 rounded text-center transition ${
                mode === "login"
                  ? "bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 shadow-2xs"
                  : "text-surface-500 hover:text-surface-900 dark:hover:text-surface-100"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setMode("register"); setError(null); }}
              className={`flex-1 py-1.5 rounded text-center transition ${
                mode === "register"
                  ? "bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 shadow-2xs"
                  : "text-surface-500 hover:text-surface-900 dark:hover:text-surface-100"
              }`}
            >
              Register
            </button>
          </div>

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50/70 p-3 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-surface-700 dark:text-surface-300 mb-1.5">
                Email address
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-surface-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@organization.com"
                  required
                  className="w-full rounded-lg border border-surface-300 bg-white py-2 pl-9 pr-3 text-sm text-surface-900 transition focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-surface-700 dark:bg-surface-850 dark:text-surface-100"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-surface-700 dark:text-surface-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-surface-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full rounded-lg border border-surface-300 bg-white py-2 pl-9 pr-10 text-sm text-surface-900 transition focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-surface-700 dark:bg-surface-850 dark:text-surface-100"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-surface-400 hover:text-surface-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {mode === "register" && (
              <div>
                <label className="block text-xs font-semibold text-surface-700 dark:text-surface-300 mb-1.5">
                  Confirm Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-surface-400" />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full rounded-lg border border-surface-300 bg-white py-2 pl-9 pr-3 text-sm text-surface-900 transition focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-surface-700 dark:bg-surface-850 dark:text-surface-100"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-surface-900 py-2.5 text-xs font-semibold text-white transition hover:bg-surface-800 disabled:opacity-50 dark:bg-surface-100 dark:text-surface-950 dark:hover:bg-white shadow-subtle cursor-pointer"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : mode === "login" ? (
                <>
                  <LogIn className="h-4 w-4" />
                  Sign In to Workspace
                </>
              ) : (
                <>
                  <UserPlus className="h-4 w-4" />
                  Create Enterprise Account
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
