import React from 'react'
import {
  ShieldCheck,
  Cpu,
  ArrowRight,
  Lock,
  Globe2,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import type { AppView, AuthUser } from '../types'

export interface LandingPageProps {
  onNavigate: (view: AppView) => void
  user?: AuthUser | null
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigate, user }) => {
  return (
    <div className="min-h-screen bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-100 flex flex-col">
      {/* Top Navigation */}
      <header className="sticky top-0 z-40 border-b border-surface-200 bg-white/90 backdrop-blur-md dark:border-surface-800 dark:bg-surface-900/90">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white font-bold text-base shadow-sm">
              M
            </div>
            <div>
              <span className="font-semibold text-base tracking-tight">Multimodal RAG</span>
              <span className="ml-2 hidden sm:inline-block text-xs font-mono text-surface-400">
                Enterprise
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {user ? (
              <Button variant="primary" size="sm" onClick={() => onNavigate('dashboard')}>
                Back to Workspace &rarr;
              </Button>
            ) : (
              <>
                <Button variant="ghost" size="sm" onClick={() => onNavigate('login')}>
                  Sign In
                </Button>
                <Button variant="primary" size="sm" onClick={() => onNavigate('register')}>
                  Get Started
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex-1 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-20 text-center">
        <div className="inline-flex mb-6">
          <Badge variant="brand" size="md" dot>
            Enterprise Document Intelligence & Multilingual RAG
          </Badge>
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-surface-900 dark:text-surface-50 max-w-3xl mx-auto leading-tight">
          Ground AI answers in verified enterprise evidence.
        </h1>

        <p className="mt-6 text-lg sm:text-xl text-surface-600 dark:text-surface-300 max-w-2xl mx-auto leading-relaxed">
          Search, interrogate, and synthesize knowledge across PDFs, spreadsheets, presentations,
          and recordings — run 100% offline with local Ollama models or securely connected to cloud providers.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5">
          {user ? (
            <Button
              size="lg"
              variant="primary"
              icon={<ArrowRight className="h-4 w-4" />}
              onClick={() => onNavigate('dashboard')}
            >
              Enter Dashboard & Workspace
            </Button>
          ) : (
            <>
              <Button
                size="lg"
                variant="primary"
                icon={<ArrowRight className="h-4 w-4" />}
                onClick={() => onNavigate('register')}
              >
                Start Enterprise Workspace
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={() => onNavigate('login')}
              >
                Sign In with Existing Account
              </Button>
            </>
          )}
        </div>

        {/* Feature Grid */}
        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
          <div className="rounded-xl border border-surface-200 bg-white p-6 dark:border-surface-800 dark:bg-surface-900 shadow-subtle">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-950/60 dark:text-brand-400 mb-4">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">
              Verifiable Evidence
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-surface-600 dark:text-surface-400">
              Every generated answer provides clickable citations linking directly to original
              paragraphs, page numbers, and highlighted source passages. Zero hallucinated citations.
            </p>
          </div>

          <div className="rounded-xl border border-surface-200 bg-white p-6 dark:border-surface-800 dark:bg-surface-900 shadow-subtle">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400 mb-4">
              <Cpu className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">
              On-Premises Privacy
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-surface-600 dark:text-surface-400">
              Complete local processing support via Ollama. All embeddings, vector indexing,
              and LLM inference can run entirely inside your private infrastructure with zero external telemetry.
            </p>
          </div>

          <div className="rounded-xl border border-surface-200 bg-white p-6 dark:border-surface-800 dark:bg-surface-900 shadow-subtle">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-50 text-sky-600 dark:bg-sky-950/60 dark:text-sky-400 mb-4">
              <Globe2 className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">
              Cross-Lingual Intelligence
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-surface-600 dark:text-surface-400">
              Query English documents in Hindi, Hinglish, Spanish, or German. Native Unicode sentence
              segmentation and protected multilingual dense retrieval across all scripts.
            </p>
          </div>
        </div>

        {/* Security & Supported Formats Strip */}
        <div className="mt-16 rounded-xl border border-surface-200 bg-white p-6 dark:border-surface-800 dark:bg-surface-900 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            <span className="text-xs font-medium text-surface-700 dark:text-surface-300">
              Multi-Tenant Data Isolation & SQLite Rate-Limiting Active
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-surface-500">
            <span>Supported:</span>
            <span className="font-mono bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded">PDF</span>
            <span className="font-mono bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded">DOCX</span>
            <span className="font-mono bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded">PPTX</span>
            <span className="font-mono bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded">XLSX</span>
            <span className="font-mono bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded">Images</span>
            <span className="font-mono bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded">Audio</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-surface-200 bg-white py-6 dark:border-surface-800 dark:bg-surface-900 text-center text-xs text-surface-500">
        <p>Multimodal Offline RAG &middot; Enterprise SaaS Platform &middot; All data remains confidential and private.</p>
      </footer>
    </div>
  )
}
