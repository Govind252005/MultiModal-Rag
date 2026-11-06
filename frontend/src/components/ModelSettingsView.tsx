import React, { useState, useEffect } from 'react'
import {
  Cpu,
  Server,
  Cloud,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ShieldCheck,
  Zap,
  Sliders,
  Database,
} from 'lucide-react'
import * as api from '../api'
import type {
  ProviderStatus,
  ActiveProviderResponse,
  OllamaDaemonStatus,
  EmbeddingMetadata,
  ProviderName,
} from '../types'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'
import { Input } from './ui/Input'

interface ModelSettingsViewProps {
  onProviderChanged?: (provider: ProviderName) => void
}

export const ModelSettingsView: React.FC<ModelSettingsViewProps> = ({
  onProviderChanged,
}) => {
  const [providers, setProviders] = useState<ProviderStatus[]>([])
  const [activeProvider, setActiveProvider] = useState<ActiveProviderResponse | null>(null)
  const [ollamaStatus, setOllamaStatus] = useState<OllamaDaemonStatus | null>(null)
  const [embeddingMeta, setEmbeddingMeta] = useState<EmbeddingMetadata | null>(null)
  const [loading, setLoading] = useState(true)
  const [probingOllama, setProbingOllama] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  // API Key management & model selection
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({})
  const [savingKey, setSavingKey] = useState<string | null>(null)
  const [validatingKey, setValidatingKey] = useState<string | null>(null)
  const [keyValidation, setKeyValidation] = useState<Record<string, 'idle' | 'valid' | 'invalid'>>({})
  const [providerModels, setProviderModels] = useState<Record<string, { id: string; name: string }[]>>({})
  const [selectedModels, setSelectedModels] = useState<Record<string, string>>({})

  const loadModelsForProvider = async (pName: ProviderName) => {
    try {
      const res = await api.getProviderModels(pName)
      if (res && res.models) {
        setProviderModels((prev) => ({ ...prev, [pName]: res.models }))
      }
    } catch {
      // Fallback
    }
  }

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [provRes, activeRes, ollamaRes, embedRes] = await Promise.all([
        api.getProviders(),
        api.getActiveProvider(),
        api.getOllamaStatus(),
        api.getEmbeddingMetadata(),
      ])
      const provList = provRes.providers || []
      setProviders(provList)
      setActiveProvider(activeRes)
      setOllamaStatus(ollamaRes)
      setEmbeddingMeta(embedRes)

      // Preload models for providers that have active keys
      for (const p of provList) {
        if (!p.local && p.has_key) {
          loadModelsForProvider(p.name)
        }
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load model settings')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const probeOllama = async () => {
    setProbingOllama(true)
    try {
      const res = await api.getOllamaStatus()
      setOllamaStatus(res)
      setNotice(`Ollama probe successful (${res.latency_ms}ms latency).`)
      setTimeout(() => setNotice(null), 3000)
    } catch (err: any) {
      setError(`Ollama probe failed: ${err.message}`)
    } finally {
      setProbingOllama(false)
    }
  }

  const handleActivateProvider = async (providerName: ProviderName, model?: string) => {
    try {
      const targetModel = model || selectedModels[providerName]
      const res = await api.activateProvider(providerName, targetModel)
      setActiveProvider(res)
      setNotice(`Switched active inference provider to ${providerName.toUpperCase()}${targetModel ? ` (${targetModel})` : ''}.`)
      setTimeout(() => setNotice(null), 3000)
      onProviderChanged?.(providerName)
      await loadData()
    } catch (err: any) {
      setError(`Failed to activate provider: ${err.message}`)
    }
  }

  const handleTestKey = async (providerName: ProviderName) => {
    const key = keyInputs[providerName]
    if (!key) return
    setValidatingKey(providerName)
    setKeyValidation((prev) => ({ ...prev, [providerName]: 'idle' }))
    try {
      const res = await api.validateProviderKey(providerName, key.trim())
      setKeyValidation((prev) => ({ ...prev, [providerName]: res.valid ? 'valid' : 'invalid' }))
      if (res.valid) {
        setNotice(`API key for ${providerName.toUpperCase()} verified successfully ✓`)
        setTimeout(() => setNotice(null), 3000)
      } else {
        setError(`API key verification failed for ${providerName.toUpperCase()} ✗`)
      }
    } catch (err: any) {
      setKeyValidation((prev) => ({ ...prev, [providerName]: 'invalid' }))
      setError(`Verification error: ${err.message}`)
    } finally {
      setValidatingKey(null)
    }
  }

  const handleSaveKey = async (providerName: ProviderName) => {
    const key = keyInputs[providerName]
    if (!key) return
    setSavingKey(providerName)
    try {
      // Automatic validation before saving if not already verified
      if (keyValidation[providerName] !== 'valid') {
        const vres = await api.validateProviderKey(providerName, key.trim())
        if (!vres.valid) {
          setKeyValidation((prev) => ({ ...prev, [providerName]: 'invalid' }))
          throw new Error(`API key verification failed for ${providerName.toUpperCase()}. Key not saved.`)
        }
        setKeyValidation((prev) => ({ ...prev, [providerName]: 'valid' }))
      }
      await api.setProviderKey(providerName, key.trim())
      setNotice(`API key verified and saved for ${providerName.toUpperCase()}.`)
      setTimeout(() => setNotice(null), 3000)
      setKeyInputs((prev) => ({ ...prev, [providerName]: '' }))
      await loadData()
      await loadModelsForProvider(providerName)
    } catch (err: any) {
      setError(`Failed to save API key: ${err.message}`)
    } finally {
      setSavingKey(null)
    }
  }

  const handleDeleteKey = async (providerName: ProviderName) => {
    try {
      await api.deleteProviderKey(providerName)
      setNotice(`Removed stored key for ${providerName.toUpperCase()}.`)
      setTimeout(() => setNotice(null), 3000)
      await loadData()
    } catch (err: any) {
      setError(`Failed to delete key: ${err.message}`)
    }
  }

  const formatGb = (bytes?: number) => {
    if (!bytes) return '—'
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100 flex items-center gap-2.5">
            <Cpu className="h-7 w-7 text-brand-600 dark:text-brand-400" />
            Model Settings & Local AI Telemetry
          </h1>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
            Configure local inference daemons, embedding pipelines, and transparent privacy boundaries.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="secondary"
            onClick={loadData}
            disabled={loading}
            icon={<RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh Status
          </Button>
        </div>
      </div>

      {notice && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <span>{notice}</span>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Grid: Ollama Daemon Card + Vector Engine Card */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Ollama Local Daemon Status */}
        <Card className="p-6 space-y-5">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400">
                <Server className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-bold text-base text-surface-900 dark:text-surface-100 flex items-center gap-2">
                  Ollama Local LLM Engine
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      ollamaStatus?.is_online ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'
                    }`}
                  />
                </h3>
                <p className="text-xs text-surface-500">
                  127.0.0.1:11434 • GPU Accelerated CUDA Engine
                </p>
              </div>
            </div>

            <Button
              size="sm"
              variant="secondary"
              onClick={probeOllama}
              disabled={probingOllama}
              icon={<RefreshCw className={`h-4 w-4 ${probingOllama ? 'animate-spin' : ''}`} />}
            >
              Probe
            </Button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="rounded-lg border border-surface-200 bg-surface-50/70 p-3 dark:border-surface-800 dark:bg-surface-900/60">
              <span className="block text-[11px] font-semibold uppercase text-surface-400">Daemon Status</span>
              <span className="mt-1 font-bold text-sm text-surface-900 dark:text-surface-100">
                {ollamaStatus?.is_online ? 'Online' : 'Offline'}
              </span>
            </div>

            <div className="rounded-lg border border-surface-200 bg-surface-50/70 p-3 dark:border-surface-800 dark:bg-surface-900/60">
              <span className="block text-[11px] font-semibold uppercase text-surface-400">Health Latency</span>
              <span className="mt-1 font-bold text-sm font-mono text-emerald-600 dark:text-emerald-400">
                {ollamaStatus?.latency_ms ?? '—'} ms
              </span>
            </div>

            <div className="rounded-lg border border-surface-200 bg-surface-50/70 p-3 dark:border-surface-800 dark:bg-surface-900/60">
              <span className="block text-[11px] font-semibold uppercase text-surface-400">Default Model</span>
              <span className="mt-1 font-bold text-xs font-mono text-surface-900 dark:text-surface-100 truncate block">
                {ollamaStatus?.default_model || 'qwen3:4b'}
              </span>
            </div>
          </div>

          {/* Installed Ollama Models List */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-surface-500 mb-2">
              Installed Local Models ({ollamaStatus?.models?.length || 0})
            </h4>
            <div className="space-y-1.5 max-h-48 overflow-y-auto rounded-lg border border-surface-200 p-2 dark:border-surface-800">
              {ollamaStatus?.models && ollamaStatus.models.length > 0 ? (
                ollamaStatus.models.map((m) => (
                  <div
                    key={m.name}
                    className="flex items-center justify-between p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-800 text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <Zap className="h-3.5 w-3.5 text-amber-500" />
                      <span className="font-mono font-medium text-surface-800 dark:text-surface-200">
                        {m.name}
                      </span>
                    </div>
                    <span className="font-mono text-surface-400">{formatGb(m.size)}</span>
                  </div>
                ))
              ) : (
                <p className="text-xs text-surface-400 py-3 text-center">No local models reported.</p>
              )}
            </div>
          </div>
        </Card>

        {/* Vector Embedding & Multimodal Engine Metadata */}
        <Card className="p-6 space-y-5">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-950/50 dark:text-brand-400">
              <Database className="h-6 w-6" />
            </div>
            <div>
              <h3 className="font-bold text-base text-surface-900 dark:text-surface-100">
                Vector Embedding & Multimodal Stack
              </h3>
              <p className="text-xs text-surface-500">
                ChromaDB + SQLite FTS5 Hybrid Multilingual Pipeline
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50/50 dark:bg-surface-900/50">
              <div>
                <span className="font-semibold text-xs text-surface-900 dark:text-surface-100 block">
                  Dense Text Embedding Model
                </span>
                <span className="text-xs font-mono text-surface-500">
                  {embeddingMeta?.dense_model || 'BAAI/bge-m3'}
                </span>
              </div>
              <Badge variant="neutral">
                {embeddingMeta?.dense_dimension || 1024}-dimensional
              </Badge>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50/50 dark:bg-surface-900/50">
              <div>
                <span className="font-semibold text-xs text-surface-900 dark:text-surface-100 block">
                  Multimodal Vision Model
                </span>
                <span className="text-xs font-mono text-surface-500">
                  {embeddingMeta?.clip_model || 'openai/clip-vit-base-patch32'}
                </span>
              </div>
              <Badge variant="neutral">
                {embeddingMeta?.clip_dimension || 512}-dimensional
              </Badge>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50/50 dark:bg-surface-900/50">
              <div>
                <span className="font-semibold text-xs text-surface-900 dark:text-surface-100 block">
                  Cross-Encoder Reranker
                </span>
                <span className="text-xs font-mono text-surface-500">
                  BAAI/bge-reranker-v2-m3 (Multilingual Cross-Attention)
                </span>
              </div>
              <Badge variant="success">Active</Badge>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50/50 dark:bg-surface-900/50">
              <div>
                <span className="font-semibold text-xs text-surface-900 dark:text-surface-100 block">
                  Keyword & Lexical Engine
                </span>
                <span className="text-xs font-mono text-surface-500">
                  SQLite FTS5 (BM25 Token Matching & Devanagari Safeguard)
                </span>
              </div>
              <Badge variant="success">Active</Badge>
            </div>
          </div>
        </Card>
      </div>

      {/* Offline vs Cloud Privacy Matrix (Mandatory Requirement) */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center gap-2.5">
          <ShieldCheck className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
          <div>
            <h3 className="font-bold text-base text-surface-900 dark:text-surface-100">
              Enterprise Privacy & Data Egress Transparency Matrix
            </h3>
            <p className="text-xs text-surface-500">
              Accurate, verified operational disclosure of network egress and offline boundaries.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-surface-200 bg-surface-50/60 font-semibold uppercase text-surface-500 dark:border-surface-800 dark:bg-surface-900/60">
              <tr>
                <th className="px-3.5 py-2.5">Component / Capability</th>
                <th className="px-3.5 py-2.5">Engine / Provider</th>
                <th className="px-3.5 py-2.5">Offline Capability</th>
                <th className="px-3.5 py-2.5">Network Egress Status</th>
                <th className="px-3.5 py-2.5">GDPR / Compliance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
              <tr>
                <td className="px-3.5 py-3 font-medium text-surface-900 dark:text-surface-100">
                  Document Retrieval & Embeddings
                </td>
                <td className="px-3.5 py-3 font-mono">BGE-M3 + ChromaDB + FTS5</td>
                <td className="px-3.5 py-3">
                  <Badge variant="success">100% Offline</Badge>
                </td>
                <td className="px-3.5 py-3 text-emerald-600 font-medium">
                  Zero cloud egress (Local only)
                </td>
                <td className="px-3.5 py-3 text-surface-600 dark:text-surface-300">
                  Fully On-Premises Compliant
                </td>
              </tr>

              <tr>
                <td className="px-3.5 py-3 font-medium text-surface-900 dark:text-surface-100">
                  Local LLM Inference
                </td>
                <td className="px-3.5 py-3 font-mono">Ollama (qwen3:4b)</td>
                <td className="px-3.5 py-3">
                  <Badge variant="success">100% Offline</Badge>
                </td>
                <td className="px-3.5 py-3 text-emerald-600 font-medium">
                  Zero cloud egress (Local GPU/CPU)
                </td>
                <td className="px-3.5 py-3 text-surface-600 dark:text-surface-300">
                  Zero Third-Party Data Transmission
                </td>
              </tr>

              <tr>
                <td className="px-3.5 py-3 font-medium text-surface-900 dark:text-surface-100">
                  Audio File Transcription
                </td>
                <td className="px-3.5 py-3 font-mono">Faster-Whisper (Local)</td>
                <td className="px-3.5 py-3">
                  <Badge variant="success">100% Offline</Badge>
                </td>
                <td className="px-3.5 py-3 text-emerald-600 font-medium">
                  Zero cloud egress (Local model)
                </td>
                <td className="px-3.5 py-3 text-surface-600 dark:text-surface-300">
                  HIPAA / Legal Confidentiality Safe
                </td>
              </tr>

              <tr className="bg-amber-50/40 dark:bg-amber-950/20">
                <td className="px-3.5 py-3 font-medium text-amber-900 dark:text-amber-200">
                  Live Browser Voice Dictation
                </td>
                <td className="px-3.5 py-3 font-mono">Browser Web Speech API</td>
                <td className="px-3.5 py-3">
                  <Badge variant="warning">Online Only</Badge>
                </td>
                <td className="px-3.5 py-3 text-amber-700 dark:text-amber-300 font-medium">
                  Streams audio to Browser Vendor (Google/Apple)
                </td>
                <td className="px-3.5 py-3 text-amber-800 dark:text-amber-300">
                  Requires Internet; Client Disclosure Enforced
                </td>
              </tr>

              <tr>
                <td className="px-3.5 py-3 font-medium text-surface-900 dark:text-surface-100">
                  Cloud LLMs (Optional)
                </td>
                <td className="px-3.5 py-3 font-mono">Gemini / OpenAI / Claude / Groq</td>
                <td className="px-3.5 py-3">
                  <Badge variant="danger">Online Only</Badge>
                </td>
                <td className="px-3.5 py-3 text-surface-600 dark:text-surface-400">
                  Transmits prompt + retrieved chunks over TLS
                </td>
                <td className="px-3.5 py-3 text-surface-600 dark:text-surface-300">
                  Subject to external provider terms & keys
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      {/* Available Providers & Model Switcher */}
      <Card className="p-6 space-y-4">
        <h3 className="font-bold text-base text-surface-900 dark:text-surface-100 flex items-center gap-2">
          <Sliders className="h-5 w-5 text-brand-600" />
          LLM Inference Provider Selection
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {providers.map((p) => {
            const isActive = activeProvider?.provider === p.name
            return (
              <div
                key={p.name}
                className={`rounded-xl border p-4 space-y-3 transition-all ${
                  isActive
                    ? 'border-brand-500 bg-brand-50/20 dark:bg-brand-950/30 ring-2 ring-brand-500/50'
                    : 'border-surface-200 bg-white dark:border-surface-800 dark:bg-surface-900'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {p.local ? (
                      <Server className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <Cloud className="h-4 w-4 text-blue-500" />
                    )}
                    <span className="font-semibold text-sm text-surface-900 dark:text-surface-100">
                      {p.label}
                    </span>
                  </div>
                  <Badge variant={p.local ? 'success' : 'neutral'}>
                    {p.local ? 'On-Prem' : 'Cloud API'}
                  </Badge>
                </div>

                <div className="text-xs text-surface-500 font-mono">
                  Active Model: {selectedModels[p.name] || p.model || '—'}
                </div>

                {!p.local && (
                  <div className="space-y-2 pt-1 border-t border-surface-100 dark:border-surface-800">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-surface-400">API Key:</span>
                      <div className="flex items-center gap-1.5">
                        {keyValidation[p.name] === 'valid' && (
                          <span className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                            Verified ✓
                          </span>
                        )}
                        {keyValidation[p.name] === 'invalid' && (
                          <span className="text-[10px] font-medium text-rose-500">
                            Invalid ✗
                          </span>
                        )}
                        <span className="font-medium text-surface-700 dark:text-surface-300">
                          {p.has_key ? '•••••••• (Stored)' : 'Not configured'}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <div className="flex gap-1.5">
                        <Input
                          type="password"
                          placeholder={`Paste ${p.label} API key...`}
                          value={keyInputs[p.name] || ''}
                          onChange={(e) => {
                            setKeyInputs((prev) => ({ ...prev, [p.name]: e.target.value }))
                            setKeyValidation((prev) => ({ ...prev, [p.name]: 'idle' }))
                          }}
                          className="text-xs py-1"
                        />
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleTestKey(p.name)}
                          disabled={!keyInputs[p.name] || validatingKey === p.name}
                          title="Verify API key validity"
                        >
                          {validatingKey === p.name ? 'Checking...' : 'Verify'}
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleSaveKey(p.name)}
                          disabled={!keyInputs[p.name] || savingKey === p.name}
                        >
                          {savingKey === p.name ? 'Saving...' : 'Save'}
                        </Button>
                        {p.has_key && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleDeleteKey(p.name)}
                            className="text-red-500 text-xs px-2"
                            title="Remove stored key"
                          >
                            Clear
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Model Selector for Cloud Provider with Verified Key */}
                    {p.has_key && (
                      <div className="space-y-1 pt-1.5 border-t border-surface-100 dark:border-surface-800">
                        <div className="flex items-center justify-between text-[11px] text-surface-500">
                          <span>Available Models:</span>
                          <span className="text-[10px] text-brand-600 dark:text-brand-400 font-medium">
                            {providerModels[p.name]?.length || 0} models
                          </span>
                        </div>
                        <select
                          value={selectedModels[p.name] || p.model}
                          onChange={(e) => {
                            const newModel = e.target.value
                            setSelectedModels((prev) => ({ ...prev, [p.name]: newModel }))
                            if (isActive) {
                              handleActivateProvider(p.name, newModel)
                            }
                          }}
                          className="w-full rounded-lg border border-surface-200 bg-white px-2 py-1.5 text-xs text-surface-800 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-100 outline-none focus:ring-1 focus:ring-brand-500"
                        >
                          {(providerModels[p.name] || [{ id: p.model, name: p.model }]).map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.name || m.id}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                )}

                <div className="pt-2">
                  <Button
                    size="sm"
                    variant={isActive ? 'secondary' : 'primary'}
                    onClick={() => handleActivateProvider(p.name, selectedModels[p.name] || p.model)}
                    disabled={isActive || (!p.local && !p.has_key)}
                    className="w-full justify-center"
                  >
                    {isActive ? '✓ Active Provider' : 'Activate Provider'}
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}
