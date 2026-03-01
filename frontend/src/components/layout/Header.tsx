import { Bell, RefreshCw } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useServerStatus } from '@/hooks/useServerStatus'

interface HeaderProps {
  title: string
  subtitle?: string
}

function StatusDot({ running }: { running?: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${
        running ? 'bg-success animate-pulse' : 'bg-danger'
      }`}
    />
  )
}

export default function Header({ title, subtitle }: HeaderProps) {
  const qc = useQueryClient()
  const { data: status } = useServerStatus()

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-panel-border bg-panel-surface">
      <div>
        <h1 className="text-lg font-semibold text-white leading-tight">{title}</h1>
        {subtitle && <p className="text-xs text-panel-muted mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-6">
        {/* Quick server status pills */}
        <div className="hidden sm:flex items-center gap-4 text-xs text-panel-muted">
          <span className="flex items-center gap-1.5">
            <StatusDot running={status?.worldserver.running} />
            World
          </span>
          <span className="flex items-center gap-1.5">
            <StatusDot running={status?.authserver.running} />
            Auth
          </span>
        </div>

        <button
          onClick={() => qc.invalidateQueries()}
          title="Refresh all data"
          className="p-2 rounded-lg text-panel-muted hover:text-white hover:bg-panel-hover transition-colors"
        >
          <RefreshCw size={16} />
        </button>

        <button
          title="Notifications"
          className="p-2 rounded-lg text-panel-muted hover:text-white hover:bg-panel-hover transition-colors"
        >
          <Bell size={16} />
        </button>
      </div>
    </header>
  )
}

