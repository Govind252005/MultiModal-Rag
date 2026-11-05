import { useEffect, useState } from 'react'
import {
  Cpu, Cloud, Check, Loader2, KeyRound, Trash2, ShieldCheck, ShieldAlert,
} from 'lucide-react'
import * as api from '../api'
import type { ProviderName, ProviderStatus } from '../types'

/**
 * Provider selector + per-user API key management.
 *
 * Local Qwen (Ollama) needs no key. Cloud providers require an API key,
 * stored encrypted on the backend (Fernet). Selecting a provider only
 * changes the final answer-generation model — retrieval is untouched.
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
      setProviders(res.providers)
      for (const p of res.providers) {
        if (!p.local && p.has_key) {
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
      await api.setProviderKey(p, keyInput.trim())
      setKeyInput('')
      setEditing(null)
      setValidState('idle')
      await refresh()
      await loadModels(p)
      onSelect(p, selectedModels[p])
    } catch (err) {
      onError((err as Error).message)
    } finally {
      setSaving(false)
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
      onError((err as Error).message)
    } finally {
      setValidating(false)
    }
  }

  async function removeKey(p: ProviderName) {
    try {
      await api.deleteProviderKey(p)
      if (provider === p) onSelect('ollama')
      await refresh()
    } catch (err) {
      onError((err as Error).message)
    }
  }

  return (
    <div className="border-t border-slate-200 px-3 py-3 dark:border-slate-800">
      {showHeading && !collapsed && (
        <p className="px-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Answer model
        </p>
      )}

      {loading ? (
        <div className="flex items-center gap-2 px-1 py-2 text-xs text-slate-400">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading providers…
        </div>
      ) : collapsed ? (
        <ul className="space-y-1.5">
          {providers.map((p) => {
            const selected = provider === p.name
            const usable = p.local || p.has_key
            return (
              <li key={p.name}>
                <button
                  onClick={() => {
                    if (usable) onSelect(p.name)
                  }}
                  title={p.label}
                  className={`flex w-full items-center justify-center rounded-xl border p-2 transition ${
                    selected
                      ? 'border-accent-300 bg-accent-50 text-accent-700 dark:border-accent-500/40 dark:bg-accent-500/10 dark:text-accent-200'
                      : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300'
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
          {providers.map((p) => {
            const selected = provider === p.name
            const usable = p.local || p.has_key
            const expanded = expandedProvider === p.name
            return (
              <li key={p.name}>
                <div
                  className={`rounded-xl border transition ${
                    selected
                      ? 'border-accent-300 bg-accent-50 dark:border-accent-500/40 dark:bg-accent-500/10'
                      : 'border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800/50'
                  } ${expanded ? 'px-2.5 py-2' : 'px-2 py-1.5'}`}
                >
                  <div className="flex items-center gap-2">
                    <button
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
                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                    >
                      <span
                        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                          selected
                            ? 'border-accent-500 bg-accent-500 text-white'
                            : 'border-slate-300 dark:border-slate-600'
                        }`}
                      >
                        {selected && <Check className="h-3 w-3" />}
                      </span>
                      {p.local ? (
                        <Cpu className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                      ) : (
                        <Cloud className="h-3.5 w-3.5 shrink-0 text-sky-500" />
                      )}
                      <span className="min-w-0 flex-1">
                        <span className={`block truncate font-medium text-slate-700 dark:text-slate-200 ${expanded ? 'text-sm' : 'text-xs'}`}>
                          {p.label}
                        </span>
                        {expanded && (
                          <span className="block truncate text-[10px] text-slate-400">
                            {selectedModels[p.name] || p.model}
                          </span>
                        )}
                      </span>
                    </button>

                    {expanded && !p.local && (
                      <div className="flex shrink-0 items-center gap-1">
                        {p.has_key ? (
                          <span title="API key saved">
                            <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                          </span>
                        ) : (
                          <span title="No API key">
                            <ShieldAlert className="h-3.5 w-3.5 text-amber-500" />
                          </span>
                        )}
                        <button
                          onClick={() => {
                            setEditing(editing === p.name ? null : p.name)
                            setKeyInput('')
                            setValidState('idle')
                          }}
                          className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
                          title={p.has_key ? 'Replace API key' : 'Add API key'}
                        >
                          <KeyRound className="h-3.5 w-3.5" />
                        </button>
                        {p.has_key && (
                          <button
                            onClick={() => removeKey(p.name)}
                            className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-500/10"
                            title="Remove API key"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Model Selector for Cloud Providers with valid Key */}
                  {!p.local && expanded && p.has_key && (
                    <div className="mt-2 border-t border-slate-100 pt-2 dark:border-slate-700/60">
                      <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                        <span>Model</span>
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
                        className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 outline-none focus:border-accent-400 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
                      >
                        {(providerModels[p.name] || [{ id: p.model, name: p.model }]).map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name || m.id}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}


                  {!p.local && expanded && editing === p.name && (
                    <div className="mt-2 space-y-1.5">
                      {!p.has_key && (
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          Add and test your API key to enable this model.
                        </p>
                      )}
                      <input
                        type="password"
                        value={keyInput}
                        onChange={(e) => {
                          setKeyInput(e.target.value)
                          setValidState('idle')
                        }}
                        placeholder={`${p.label} API key`}
                        className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-accent-400 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
                      />
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => saveKey(p.name)}
                          disabled={saving || !keyInput.trim()}
                          className="flex items-center gap-1 rounded-lg bg-accent-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-700 disabled:opacity-50"
                        >
                          {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                          Save
                        </button>
                        <button
                          onClick={() => validateKey(p.name)}
                          disabled={validating || !keyInput.trim()}
                          className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                        >
                          {validating ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Test'}
                        </button>
                        {validState === 'valid' && (
                          <span className="text-xs font-medium text-emerald-500">Valid ✓</span>
                        )}
                        {validState === 'invalid' && (
                          <span className="text-xs font-medium text-red-500">Invalid ✗</span>
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
