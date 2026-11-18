import React from 'react'
import {
  ShieldCheck,
  Cpu,
  ArrowRight,
  Lock,
  Globe2,
  FileText,
  ImageIcon,
  Mic,
  Server,
  Terminal,
  Activity,
  Layers,
  CheckCircle2,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import type { AppView, AuthUser } from '../types'

export interface LandingPageProps {
  onNavigate: (view: AppView) => void
  user?: AuthUser | null
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigate, user }) => {
  return (
    <div className="min-h-screen bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-100 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 border-b border-surface-200 bg-white/95 backdrop-blur-md dark:border-surface-800 dark:bg-surface-900/95">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-900 text-surface-50 dark:bg-surface-100 dark:text-surface-950 font-mono font-bold text-base shadow-sm">
              M
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm tracking-tight text-surface-900 dark:text-surface-100">
                  Multimodal RAG
                </span>
                <span className="rounded bg-surface-200 dark:bg-surface-800 px-1.5 py-0.2 font-mono text-[10px] font-semibold text-surface-600 dark:text-surface-400">
                  ENTERPRISE v2.0
                </span>
              </div>
              <span className="hidden sm:block text-[11px] text-surface-400">
                Local Privacy &amp; Enterprise Cloud Intelligence
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full border border-surface-200 dark:border-surface-800 bg-surface-100/60 dark:bg-surface-850/60 text-xs font-mono text-surface-600 dark:text-surface-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>HYBRID ENGINE: LOCAL + CLOUD</span>
            </div>

            {user ? (
              <Button variant="primary" size="sm" onClick={() => onNavigate('dashboard')}>
                Enter Workspace &rarr;
              </Button>
            ) : (
              <>
                <Button variant="ghost" size="sm" onClick={() => onNavigate('login')}>
                  Sign In
                </Button>
                <Button variant="primary" size="sm" onClick={() => onNavigate('register')}>
                  Open Console
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex-1 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-14 pb-16">
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex">
            <div className="inline-flex items-center gap-2 rounded-full border border-surface-300 dark:border-surface-700 bg-surface-100 dark:bg-surface-850 px-3 py-1 text-xs font-mono font-medium text-surface-700 dark:text-surface-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              LOCAL ON-PREM (CUDA) + CLOUD (OPENAI, GEMINI, CLAUDE, GROQ)
            </div>
          </div>

          <h1 className="text-3xl sm:text-5xl font-bold tracking-tight text-surface-900 dark:text-surface-50 leading-tight">
            High-precision multimodal retrieval with verifiable provenance.
          </h1>

          <p className="text-base sm:text-lg text-surface-600 dark:text-surface-400 leading-relaxed max-w-2xl mx-auto">
            Interrogate PDFs, technical drawings, financial ledgers, and audio briefings. Every answer is synthesized with exact bounding-box and paragraph citations.
          </p>

          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
            {user ? (
              <Button
                size="lg"
                variant="primary"
                icon={<ArrowRight className="h-4 w-4" />}
                onClick={() => onNavigate('dashboard')}
              >
                Go to Workspace Dashboard
              </Button>
            ) : (
              <>
                <Button
                  size="lg"
                  variant="primary"
                  icon={<ArrowRight className="h-4 w-4" />}
                  onClick={() => onNavigate('register')}
                >
                  Launch Local Workspace
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  onClick={() => onNavigate('login')}
                >
                  Sign In with Existing Session
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Architectural Blueprint Hero Diagram */}
        <div className="mt-14 rounded-xl border border-surface-200 dark:border-surface-800 bg-white dark:bg-surface-900 p-6 shadow-subtle">
          <div className="flex items-center justify-between border-b border-surface-200 dark:border-surface-800 pb-3 mb-6">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-surface-400" />
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-surface-700 dark:text-surface-300">
                End-to-End Pipeline Execution Architecture
              </span>
            </div>
            <span className="font-mono text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
              Local Privacy &amp; Cloud Flexibility
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Stage 1: Ingestion */}
            <div className="rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-surface-900 dark:text-surface-100 uppercase">
                  01 / Ingestion Engine
                </span>
                <span className="text-[10px] font-mono text-surface-400">Raw Input</span>
              </div>
              <div className="space-y-2 text-xs text-surface-600 dark:text-surface-400">
                <div className="flex items-center gap-2 rounded bg-white dark:bg-surface-900 p-2 border border-surface-200/60 dark:border-surface-800/60">
                  <FileText className="h-4 w-4 text-brand-600" />
                  <span>PDF / DOCX / PPTX / XLSX layout parsing</span>
                </div>
                <div className="flex items-center gap-2 rounded bg-white dark:bg-surface-900 p-2 border border-surface-200/60 dark:border-surface-800/60">
                  <ImageIcon className="h-4 w-4 text-brand-600" />
                  <span>PP-OCRv6 text &amp; CLIP visual indexing</span>
                </div>
                <div className="flex items-center gap-2 rounded bg-white dark:bg-surface-900 p-2 border border-surface-200/60 dark:border-surface-800/60">
                  <Mic className="h-4 w-4 text-brand-600" />
                  <span>Whisper speech audio transcription</span>
                </div>
              </div>
            </div>

            {/* Stage 2: Retrieval Fusion */}
            <div className="rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-surface-900 dark:text-surface-100 uppercase">
                  02 / Hybrid Retrieval
                </span>
                <span className="text-[10px] font-mono text-surface-400">RRF Fusion</span>
              </div>
              <div className="space-y-2 text-xs text-surface-600 dark:text-surface-400">
                <div className="flex items-center gap-2 rounded bg-white dark:bg-surface-900 p-2 border border-surface-200/60 dark:border-surface-800/60">
                  <Layers className="h-4 w-4 text-amber-600" />
                  <span>Reciprocal Rank Fusion (k = 60)</span>
                </div>
                <div className="flex items-center gap-2 rounded bg-white dark:bg-surface-900 p-2 border border-surface-200/60 dark:border-surface-800/60">
                  <Globe2 className="h-4 w-4 text-amber-600" />
                  <span>Dense multilingual embeddings (MiniLM-L12)</span>
                </div>
                <div className="flex items-center gap-2 rounded bg-white dark:bg-surface-900 p-2 border border-surface-200/60 dark:border-surface-800/60">
                  <ShieldCheck className="h-4 w-4 text-amber-600" />
                  <span>Cross-encoder reranking &amp; hallucination guard</span>
                </div>
              </div>
            </div>

            {/* Stage 3: Inference & Grounding */}
            <div className="rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-850 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-surface-900 dark:text-surface-100 uppercase">
                  03 / Local Synthesis
                </span>
                <span className="text-[10px] font-mono text-surface-400">Grounding</span>
              </div>
              <div className="space-y-2 text-xs text-surface-600 dark:text-surface-400">
                <div className="flex items-center gap-2 rounded bg-white dark:bg-surface-900 p-2 border border-surface-200/60 dark:border-surface-800/60">
                  <Cpu className="h-4 w-4 text-emerald-600" />
                  <span>Ollama Qwen2.5:7b-instruct on CUDA</span>
                </div>
                <div className="flex items-center gap-2 rounded bg-white dark:bg-surface-900 p-2 border border-surface-200/60 dark:border-surface-800/60">
                  <Activity className="h-4 w-4 text-emerald-600" />
                  <span>Real-time SSE token &amp; TTFT telemetry</span>
                </div>
                <div className="flex items-center gap-2 rounded bg-white dark:bg-surface-900 p-2 border border-surface-200/60 dark:border-surface-800/60">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <span>Verifiable numbered superscript citations</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bento Grid: Core Enterprise Features */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="rounded-xl border border-surface-200 dark:border-surface-800 bg-white dark:bg-surface-900 p-6 shadow-subtle">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-800 text-surface-800 dark:text-surface-200 mb-4">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-semibold tracking-tight text-surface-900 dark:text-surface-100">
              Verifiable Evidence Provenance
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-surface-500 dark:text-surface-400">
              Every generated statement is bound to numbered source citations. Clicking a citation jumps directly to the matching page, highlighted text span, or audio timecode.
            </p>
          </div>

          <div className="rounded-xl border border-surface-200 dark:border-surface-800 bg-white dark:bg-surface-900 p-6 shadow-subtle">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-800 text-surface-800 dark:text-surface-200 mb-4">
              <Server className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-semibold tracking-tight text-surface-900 dark:text-surface-100">
              On-Premises Privacy &amp; Cloud Flexibility
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-surface-500 dark:text-surface-400">
              Run 100% locally with Ollama &amp; CUDA acceleration with zero cloud egress, or seamlessly connect your own API keys for Groq, Google Gemini, OpenAI, and Anthropic Claude.
            </p>
          </div>

          <div className="rounded-xl border border-surface-200 dark:border-surface-800 bg-white dark:bg-surface-900 p-6 shadow-subtle">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-800 text-surface-800 dark:text-surface-200 mb-4">
              <Globe2 className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-semibold tracking-tight text-surface-900 dark:text-surface-100">
              Multilingual Cross-Lingual RAG
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-surface-500 dark:text-surface-400">
              Query complex English documentation in Hindi, Hinglish, Spanish, or German. Multilingual sentence segmentation ensures precision across all scripts.
            </p>
          </div>
        </div>

        {/* Security & Specification Strip */}
        <div className="mt-8 rounded-xl border border-surface-200 dark:border-surface-800 bg-surface-100/70 dark:bg-surface-900/70 p-4 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
          <div className="flex items-center gap-2 text-surface-700 dark:text-surface-300">
            <Lock className="h-4 w-4 text-emerald-600" />
            <span>SQLite Rate-Limiter · Argon2 Password Hashing · Isolated Tenant Schemas</span>
          </div>
          <div className="flex items-center gap-2 text-surface-500">
            <span className="rounded bg-white dark:bg-surface-800 px-2 py-0.5 border border-surface-200 dark:border-surface-700">PDF</span>
            <span className="rounded bg-white dark:bg-surface-800 px-2 py-0.5 border border-surface-200 dark:border-surface-700">DOCX</span>
            <span className="rounded bg-white dark:bg-surface-800 px-2 py-0.5 border border-surface-200 dark:border-surface-700">PPTX</span>
            <span className="rounded bg-white dark:bg-surface-800 px-2 py-0.5 border border-surface-200 dark:border-surface-700">XLSX</span>
            <span className="rounded bg-white dark:bg-surface-800 px-2 py-0.5 border border-surface-200 dark:border-surface-700">PNG/JPG</span>
            <span className="rounded bg-white dark:bg-surface-800 px-2 py-0.5 border border-surface-200 dark:border-surface-700">WAV/MP3</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-surface-200 bg-white py-6 dark:border-surface-800 dark:bg-surface-900 text-center text-xs text-surface-500 font-mono">
        <p>MULTIMODAL RAG ENTERPRISE &middot; LOCAL ON-PREM + CLOUD MODEL INTEGRATION &middot; ZERO DATA LEAKAGE</p>
      </footer>
    </div>
  )
}
