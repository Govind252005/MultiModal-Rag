import React, { useState } from 'react'
import { Eye, EyeOff, Lock, Mail, ArrowRight, ShieldCheck, AlertCircle } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import * as api from '../api'
import type { AppView, AuthUser } from '../types'

export interface AuthPageProps {
  initialMode?: 'login' | 'register'
  onSuccess: (user: AuthUser) => void
  onNavigate: (view: AppView) => void
}

export const AuthPage: React.FC<AuthPageProps> = ({
  initialMode = 'login',
  onSuccess,
  onNavigate,
}) => {
  const [isRegister, setIsRegister] = useState(initialMode === 'register')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    const cleanEmail = email.trim()
    if (!cleanEmail || !password) {
      setError('Please fill in all required fields.')
      return
    }

    if (isRegister) {
      if (password.length < 8) {
        setError('Password must be at least 8 characters long.')
        return
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match.')
        return
      }
    }

    setLoading(true)
    try {
      if (isRegister) {
        const res = await api.register(cleanEmail, password)
        api.setToken(res.token)
        onSuccess(res.user)
      } else {
        const res = await api.login(cleanEmail, password)
        api.setToken(res.token)
        onSuccess(res.user)
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-50 dark:bg-surface-950 flex flex-col justify-center items-center px-4 py-12 font-sans text-surface-900 dark:text-surface-100">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-between">
          <button
            type="button"
            onClick={() => onNavigate('landing')}
            className="inline-flex items-center gap-1.5 text-xs font-mono text-surface-500 hover:text-surface-800 dark:text-surface-400 dark:hover:text-surface-200 transition-colors"
          >
            &larr; BACK TO OVERVIEW
          </button>
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-600 dark:text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>ENTERPRISE SECURE</span>
          </div>
        </div>

        {/* Header Branding */}
        <div className="text-center mb-6">
          <div
            onClick={() => onNavigate('landing')}
            className="inline-flex cursor-pointer items-center justify-center h-11 w-11 rounded-lg bg-surface-900 text-surface-50 dark:bg-surface-100 dark:text-surface-950 font-mono font-bold text-lg shadow-subtle mb-3"
          >
            M
          </div>
          <h2 className="text-xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
            {isRegister ? 'Provision Workspace Access' : 'Authenticate Session'}
          </h2>
          <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">
            {isRegister
              ? 'Initialize isolated tenant repository with encrypted credentials'
              : 'Enter enterprise credentials to access active RAG sessions'}
          </p>
        </div>

        {/* Auth Card */}
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 sm:p-7 shadow-subtle">
          {/* Segmented Control */}
          <div className="flex rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-100 dark:bg-surface-950 p-1 mb-5 text-xs font-medium">
            <button
              type="button"
              onClick={() => { setIsRegister(false); setError(null); }}
              className={`flex-1 py-1.5 rounded text-center transition font-mono ${
                !isRegister
                  ? 'bg-white dark:bg-surface-850 text-surface-900 dark:text-surface-100 shadow-2xs font-semibold'
                  : 'text-surface-500 hover:text-surface-900 dark:hover:text-surface-100'
              }`}
            >
              SIGN IN
            </button>
            <button
              type="button"
              onClick={() => { setIsRegister(true); setError(null); }}
              className={`flex-1 py-1.5 rounded text-center transition font-mono ${
                isRegister
                  ? 'bg-white dark:bg-surface-850 text-surface-900 dark:text-surface-100 shadow-2xs font-semibold'
                  : 'text-surface-500 hover:text-surface-900 dark:hover:text-surface-100'
              }`}
            >
              REGISTER
            </button>
          </div>

          {error && (
            <div className="mb-5 flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50/70 p-3 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-500 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Enterprise Email"
              type="email"
              autoComplete="email"
              placeholder="operator@organization.internal"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              leftIcon={<Mail className="h-4 w-4" />}
              required
            />

            <div className="relative">
              <Input
                label="Master Passphrase"
                type={showPassword ? 'text' : 'password'}
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                leftIcon={<Lock className="h-4 w-4" />}
                rightIcon={
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-surface-400 hover:text-surface-600 dark:hover:text-surface-200"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
                required
              />
            </div>

            {isRegister && (
              <Input
                label="Confirm Passphrase"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="••••••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                leftIcon={<Lock className="h-4 w-4" />}
                required
              />
            )}

            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={loading}
              className="w-full mt-2"
              icon={<ArrowRight className="h-4 w-4" />}
            >
              {isRegister ? 'Provision Workspace' : 'Authenticate Console'}
            </Button>
          </form>
        </div>

        {/* Security badge at bottom */}
        <div className="mt-6 flex items-center justify-center gap-2 text-xs font-mono text-surface-400">
          <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-500" />
          <span>ARGON2 SECURED &middot; LOCAL ISOLATION</span>
        </div>
      </div>
    </div>
  )
}
