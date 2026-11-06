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
      'inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none select-none rounded-lg'

    const sizeClasses = {
      sm: 'text-xs px-2.5 py-1.5 gap-1.5',
      md: 'text-sm px-3.5 py-2 gap-2',
      lg: 'text-base px-5 py-2.5 gap-2.5',
    }[size]

    const variantClasses = {
      primary:
        'bg-brand-600 hover:bg-brand-700 text-white shadow-sm active:bg-brand-800 dark:bg-brand-500 dark:hover:bg-brand-600',
      secondary:
        'bg-surface-100 hover:bg-surface-200 text-surface-900 border border-surface-200 active:bg-surface-300 dark:bg-surface-800 dark:hover:bg-surface-700 dark:text-surface-100 dark:border-surface-700',
      outline:
        'bg-transparent border border-surface-300 hover:bg-surface-100 text-surface-700 dark:border-surface-700 dark:text-surface-300 dark:hover:bg-surface-800',
      ghost:
        'bg-transparent hover:bg-surface-100 text-surface-700 dark:text-surface-300 dark:hover:bg-surface-800',
      danger:
        'bg-rose-600 hover:bg-rose-700 text-white shadow-sm active:bg-rose-800 dark:bg-rose-500 dark:hover:bg-rose-600',
    }[variant]

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`${baseClasses} ${sizeClasses} ${variantClasses} ${className}`}
        {...props}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin text-current" />
        ) : (
          icon && <span className="shrink-0">{icon}</span>
        )}
        {children}
      </button>
    )
  },
)

Button.displayName = 'Button'
