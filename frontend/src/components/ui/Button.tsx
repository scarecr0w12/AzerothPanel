import clsx from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'secondary' | 'danger' | 'success' | 'ghost'
type Size = 'sm' | 'md' | 'lg'

const VARIANT: Record<Variant, string> = {
  primary:   'bg-brand hover:bg-brand-hover text-white',
  secondary: 'bg-panel-hover hover:bg-panel-border text-gray-300 border border-panel-border',
  danger:    'bg-danger/10 hover:bg-danger/20 text-danger border border-danger/30',
  success:   'bg-success/10 hover:bg-success/20 text-success border border-success/30',
  ghost:     'hover:bg-panel-hover text-gray-400 hover:text-white',
}

const SIZE: Record<Size, string> = {
  sm:  'text-xs px-3 py-1.5 gap-1.5',
  md:  'text-sm px-4 py-2 gap-2',
  lg:  'text-base px-5 py-2.5 gap-2.5',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: ReactNode
  children?: ReactNode
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center font-medium rounded-lg',
        'transition-all duration-150 focus-visible:outline-none focus-visible:ring-2',
        'focus-visible:ring-brand/50 disabled:opacity-50 disabled:cursor-not-allowed',
        VARIANT[variant],
        SIZE[size],
        className
      )}
      {...props}
    >
      {loading ? <Loader2 size={14} className="animate-spin" /> : icon}
      {children}
    </button>
  )
}

