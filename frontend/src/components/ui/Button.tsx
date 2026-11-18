import React from 'react'
import { Loader2 } from 'lucide-react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      loading = false,
      icon,
      disabled,
      className = '',
      ...props
    },
    ref,
  ) => {
    const baseClasses =
      'inline-flex items-center justify-center font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500 disabled:opacity-40 disabled:pointer-events-none select-none rounded-lg cursor-pointer'

    const sizeClasses = {
      sm: 'text-xs px-2.5 py-1.5 gap-1.5',
      md: 'text-xs px-3.5 py-2 gap-2 tracking-tight',
      lg: 'text-sm px-4 py-2.5 gap-2.5',
    }[size]

    const variantClasses = {
      primary:
        'bg-surface-900 text-surface-50 border border-surface-800 hover:bg-surface-800 active:bg-surface-950 dark:bg-surface-100 dark:text-surface-950 dark:border-surface-200 dark:hover:bg-white shadow-subtle',
      secondary:
        'bg-surface-100 text-surface-900 border border-surface-200 hover:bg-surface-200/80 active:bg-surface-300 dark:bg-surface-850 dark:text-surface-100 dark:border-surface-800 dark:hover:bg-surface-800 shadow-subtle',
      outline:
        'bg-transparent border border-surface-200 text-surface-700 hover:bg-surface-100 hover:text-surface-900 dark:border-surface-800 dark:text-surface-300 dark:hover:bg-surface-850 dark:hover:text-surface-100',
      ghost:
        'bg-transparent hover:bg-surface-100 text-surface-600 hover:text-surface-900 dark:text-surface-400 dark:hover:bg-surface-850 dark:hover:text-surface-200',
      danger:
        'bg-rose-600 hover:bg-rose-700 text-white border border-rose-700 active:bg-rose-800 dark:bg-rose-950/80 dark:border-rose-800/80 dark:text-rose-300 dark:hover:bg-rose-900 shadow-subtle',
    }[variant]

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`${baseClasses} ${sizeClasses} ${variantClasses} ${className}`}
        {...props}
      >
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-current" />
        ) : (
          icon && <span className="shrink-0">{icon}</span>
        )}
        {children}
      </button>
    )
  },
)

Button.displayName = 'Button'
