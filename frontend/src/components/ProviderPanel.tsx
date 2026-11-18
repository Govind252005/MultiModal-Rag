import { useEffect, useState } from 'react'
import {
  Cpu, Cloud, Check, Loader2, KeyRound, Trash2, ShieldCheck, ShieldAlert,
} from 'lucide-react'
import * as api from '../api'
import type { ProviderName, ProviderStatus } from '../types'

/**
 * Provider selector + per-user API key management.
 * Clean, industrial precision styling.
 */
export default function ProviderPanel({
  provider,
  onSelect,
  onError,
  collapsed,
  showHeading = true,
}: {
  provider: ProviderName
  onSelect: (p: ProviderName, model?: string) => void
  onError: (msg: string) => void
  collapsed: boolean
  showHeading?: boolean
}) {
  const [providers, setProviders] = useState<ProviderStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<ProviderName | null>(null)
  const [keyInput, setKeyInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validState, setValidState] = useState<'idle' | 'valid' | 'invalid'>('idle')
  const [expandedProvider, setExpandedProvider] = useState<ProviderName>(provider)
  const [providerModels, setProviderModels] = useState<Record<string, { id: string; name: string }[]>>({})
  const [selectedModels, setSelectedModels] = useState<Record<string, string>>({})
  const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({})

  useEffect(() => {
    setExpandedProvider(provider)
  }, [provider])

  async function loadModels(p: ProviderName) {
    if (providerModels[p]?.length || loadingModels[p]) return
    setLoadingModels((prev) => ({ ...prev, [p]: true }))
    try {
      const res = await api.getProviderModels(p)
      if (res && res.models) {
        setProviderModels((prev) => ({ ...prev, [p]: res.models }))
        if (!selectedModels[p] && res.models.length > 0) {
          setSelectedModels((prev) => ({ ...prev, [p]: res.models[0].id }))
        }
      }
    } catch {
      // Non-fatal, fallback to default
    } finally {
      setLoadingModels((prev) => ({ ...prev, [p]: false }))
    }
  }

  async function refresh() {
    try {
      const res = await api.getProviders()
      const list = res?.providers || []
      setProviders(list)
      for (const p of list) {
        if (p.local || p.has_key) {
          loadModels(p.name)
        }
      }
    } catch (err) {
      onError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function saveKey(p: ProviderName) {
    if (!keyInput.trim()) return
    setSaving(true)
    try {
      if (validState !== 'valid') {
        setValidating(true)
        const vres = await api.validateProviderKey(p, keyInput.trim())
        setValidating(false)
        if (!vres.valid) {
          setValidState('invalid')
          throw new Error(`API key verification failed for ${p}. Key not saved.`)
        }
        setValidState('valid')
      }
      await api.setProviderKey(p, keyInput.trim())
      setKeyInput('')
      setEditing(null)
      setValidState('idle')
      await refresh()
    } catch (err) {
      onError((err as Error).message)
    } finally {
      setSaving(false)
      setValidating(false)
    }
  }

  async function validateKey(p: ProviderName) {
    if (!keyInput.trim()) return
    setValidating(true)
    setValidState('idle')
    try {
      const res = await api.validateProviderKey(p, keyInput.trim())
      setValidState(res.valid ? 'valid' : 'invalid')
    } catch (err) {
      setValidState('invalid')
      onError((err as Error).message)
    } finally {
      setValidating(false)
    }
  }

  async function removeKey(p: ProviderName) {
    if (!confirm(`Remove API key for ${p}?`)) return
    try {
      await api.deleteProviderKey(p)
      if (provider === p) onSelect('ollama')
      await refresh()
    } catch (err) {
      onError((err as Error).message)
    }
  }

  const safeProviders = Array.isArray(providers) ? providers : []

  return (
    <div className="space-y-2">
      {showHeading && (
        <p className="px-1 text-[10px] font-mono font-semibold uppercase tracking-wider text-surface-400">
          Reasoning Model
        </p>
      )}

      {loading ? (
        <div className="flex items-center gap-2 px-1 py-2 text-xs font-mono text-surface-400">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading providers…
        </div>
      ) : collapsed ? (
        <ul className="space-y-1.5">
          {safeProviders.map((p) => {
            const selected = provider === p.name
            const usable = p.local || p.has_key
            return (
              <li key={p.name}>
                <button
                  type="button"
                  onClick={() => {
                    if (usable) onSelect(p.name)
                  }}
                  title={p.label}
                  className={`flex w-full items-center justify-center rounded-lg border p-2 transition cursor-pointer ${
                    selected
                      ? 'border-surface-800 bg-surface-900 text-surface-50 dark:border-surface-200 dark:bg-surface-100 dark:text-surface-950'
                      : 'border-surface-200 bg-white text-surface-500 hover:border-surface-300 dark:border-surface-700 dark:bg-surface-850 dark:text-surface-300'
                  }`}
                >
                  {p.local ? (
                    <Cpu className="h-4 w-4" />
                  ) : (
                    <Cloud className="h-4 w-4" />
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      ) : (
        <ul className="space-y-1.5">
          {safeProviders.map((p) => {
            const selected = provider === p.name
            const usable = p.local || p.has_key
            const expanded = expandedProvider === p.name
            return (
              <li key={p.name}>
                <div
                  className={`rounded-lg border transition ${
                    selected
                      ? 'border-surface-400 bg-surface-100/90 dark:border-surface-600 dark:bg-surface-800 ring-1 ring-surface-300 dark:ring-surface-700'
                      : 'border-surface-200 bg-white hover:border-surface-300 dark:border-surface-800 dark:bg-surface-900'
                  } ${expanded ? 'p-2.5' : 'px-2.5 py-1.5'}`}
                >
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setExpandedProvider(p.name)
                        if (usable) {
                          onSelect(p.name, selectedModels[p.name])
                          setEditing(null)
                          setValidState('idle')
                          return
                        }
                        if (!p.local) {
                          setEditing(p.name)
                          setValidState('idle')
                        }
                      }}
                      className="flex min-w-0 flex-1 items-center gap-2 text-left cursor-pointer"
                    >
                      <span
                        className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border ${
                          selected
                            ? 'border-surface-900 bg-surface-900 text-white dark:border-surface-100 dark:bg-surface-100 dark:text-surface-950'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      >
                        {selected && <Check className="h-2.5 w-2.5" />}
                      </span>
                      {p.local ? (
                        <Cpu className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                      ) : (
                        <Cloud className="h-3.5 w-3.5 shrink-0 text-sky-500" />
                      )}
                      <span className="min-w-0 flex-1">
                        <span className={`block truncate font-medium text-surface-800 dark:text-surface-100 ${expanded ? 'text-xs' : 'text-[11px]'}`}>
                          {p.label}
                        </span>
                        {expanded && (
                          <span className="block truncate font-mono text-[10px] text-surface-400">
                            {selectedModels[p.name] || p.model}
                          </span>
                        )}
                      </span>
                    </button>

                    {expanded && !p.local && (
                      <div className="flex shrink-0 items-center gap-1">
                        {p.has_key ? (
                          <span title="API key active">
                            <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                          </span>
                        ) : (
                          <span title="No API key provided">
                            <ShieldAlert className="h-3.5 w-3.5 text-amber-500" />
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(editing === p.name ? null : p.name)
                            setKeyInput('')
                            setValidState('idle')
                          }}
                          className="rounded p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600 dark:hover:bg-surface-800 cursor-pointer"
                          title={p.has_key ? 'Replace key' : 'Add key'}
                        >
                          <KeyRound className="h-3 w-3" />
                        </button>
                        {p.has_key && (
                          <button
                            type="button"
                            onClick={() => removeKey(p.name)}
                            className="rounded p-1 text-surface-400 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40 cursor-pointer"
                            title="Remove key"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Model Selector */}
                  {expanded && (p.local || p.has_key) && (
                    <div className="mt-2 border-t border-surface-100 pt-2 dark:border-surface-800">
                      <div className="flex items-center justify-between text-[10px] font-mono text-surface-400 mb-1">
                        <span>MODEL IDENTIFIER</span>
                        {loadingModels[p.name] && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
                      </div>
                      <select
                        value={selectedModels[p.name] || p.model}
                        onChange={(e) => {
                          const newModel = e.target.value
                          setSelectedModels((prev) => ({ ...prev, [p.name]: newModel }))
                          if (selected) {
                            onSelect(p.name, newModel)
                          }
                        }}
                        className="w-full rounded border border-surface-200 bg-white px-2 py-1 text-xs font-mono text-surface-800 outline-none focus:border-brand-500 dark:border-surface-700 dark:bg-surface-850 dark:text-surface-100"
                      >
                        {(providerModels[p.name] || [{ id: p.model, name: p.model }]).map((m) => (
                          <option key={m.id} value={m.id} className="dark:bg-surface-850 dark:text-surface-100">
                            {m.name || m.id}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {!p.local && expanded && editing === p.name && (
                    <div className="mt-2 space-y-1.5">
                      {!p.has_key && (
                        <p className="text-[10px] font-mono text-surface-400">
                          Configure API credentials for {p.label}:
                        </p>
                      )}
                      <input
                        type="password"
                        value={keyInput}
                        onChange={(e) => {
                          setKeyInput(e.target.value)
                          setValidState('idle')
                        }}
                        placeholder={`${p.label} key`}
                        className="w-full rounded border border-surface-200 bg-white px-2 py-1 text-xs font-mono text-surface-800 outline-none focus:border-brand-500 dark:border-surface-700 dark:bg-surface-850 dark:text-surface-100"
                      />
                      <div className="flex items-center gap-1.5 pt-1">
                        <button
                          type="button"
                          onClick={() => saveKey(p.name)}
                          disabled={saving || !keyInput.trim()}
                          className="flex items-center gap-1 rounded bg-surface-900 px-2 py-0.5 text-xs font-mono font-medium text-white hover:bg-surface-800 disabled:opacity-50 dark:bg-surface-100 dark:text-surface-950 dark:hover:bg-white cursor-pointer"
                        >
                          {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={() => validateKey(p.name)}
                          disabled={validating || !keyInput.trim()}
                          className="flex items-center gap-1 rounded border border-surface-200 px-2 py-0.5 text-xs font-mono font-medium text-surface-600 hover:bg-surface-50 disabled:opacity-50 dark:border-surface-700 dark:text-surface-300 dark:hover:bg-surface-800 cursor-pointer"
                        >
                          {validating ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Test'}
                        </button>
                        {validState === 'valid' && (
                          <span className="font-mono text-xs text-emerald-600 dark:text-emerald-400 font-semibold">Valid ✓</span>
                        )}
                        {validState === 'invalid' && (
                          <span className="font-mono text-xs text-rose-600 dark:text-rose-400 font-semibold">Invalid ✗</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
