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
    <div className="min-h-screen bg-surface-50 dark:bg-surface-950 flex flex-col justify-center items-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Header Branding */}
        <div className="text-center mb-8">
          <div
            onClick={() => onNavigate('landing')}
            className="inline-flex cursor-pointer items-center justify-center h-12 w-12 rounded-xl bg-brand-600 text-white font-bold text-xl shadow-card mb-4"
          >
            M
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
            {isRegister ? 'Create your enterprise workspace' : 'Sign in to Multimodal RAG'}
          </h2>
          <p className="mt-2 text-xs text-surface-500 dark:text-surface-400">
            {isRegister
              ? 'Access private offline and cloud-connected document intelligence'
              : 'Enter your credentials to access your session library'}
          </p>
        </div>

        {/* Auth Card */}
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-2xl p-6 sm:p-8 shadow-card">
          {error && (
            <div className="mb-5 flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50/70 p-3 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-500 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Work Email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              leftIcon={<Mail className="h-4 w-4" />}
              required
            />

            <div className="relative">
              <Input
                label="Password"
                type={showPassword ? 'text' : 'password'}
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                placeholder="Your password"
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
                label="Confirm Password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="Re-enter password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                leftIcon={<Lock className="h-4 w-4" />}
                required
              />
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full mt-2"
              icon={<ArrowRight className="h-4 w-4" />}
            >
              {isRegister ? 'Create Account' : 'Sign In'}
            </Button>
          </form>

          {/* Toggle between Login and Register */}
          <div className="mt-6 pt-5 border-t border-surface-100 dark:border-surface-800 text-center text-xs text-surface-500">
            {isRegister ? (
              <p>
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setIsRegister(false)
                    setError(null)
                  }}
                  className="font-medium text-brand-600 hover:text-brand-500 dark:text-brand-400 underline"
                >
                  Sign in
                </button>
              </p>
            ) : (
              <p>
                Don't have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setIsRegister(true)
                    setError(null)
                  }}
                  className="font-medium text-brand-600 hover:text-brand-500 dark:text-brand-400 underline"
                >
                  Create one now
                </button>
              </p>
            )}
          </div>
        </div>

        {/* Security badge at bottom */}
        <div className="mt-8 flex items-center justify-center gap-1.5 text-xs text-surface-400">
          <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-500" />
          <span>PBKDF2 Password Hashing &middot; Multi-Tenant Encrypted Sessions</span>
        </div>
      </div>
    </div>
  )
}
