import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Server, ScrollText, Users, Database,
  Download, Hammer, LogOut, ChevronLeft, ChevronRight, Shield, Settings,
} from 'lucide-react'
import clsx from 'clsx'
import { useUIStore, useAuthStore } from '@/store'

const NAV_ITEMS = [
  { to: '/',            icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/server',      icon: Server,          label: 'Server Control' },
  { to: '/logs',        icon: ScrollText,      label: 'Log Viewer' },
  { to: '/players',     icon: Users,           label: 'Players' },
  { to: '/database',    icon: Database,        label: 'Database' },
  { to: '/compilation', icon: Hammer,          label: 'Compilation' },
  { to: '/installation',icon: Download,        label: 'Installation' },
  { to: '/settings',    icon: Settings,        label: 'Settings' },
]

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const { clearAuth, username } = useAuthStore()

  return (
    <aside
      className={clsx(
        'flex flex-col h-screen bg-panel-surface border-r border-panel-border',
        'transition-all duration-300 select-none',
        sidebarCollapsed ? 'w-16' : 'w-56'
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-panel-border">
        <Shield className="text-brand shrink-0" size={24} />
        {!sidebarCollapsed && (
          <span className="font-bold text-lg text-white tracking-tight">AzerothPanel</span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 space-y-1 px-2">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium',
                'transition-colors duration-150',
                isActive
                  ? 'bg-brand/20 text-brand-light'
                  : 'text-gray-400 hover:bg-panel-hover hover:text-white'
              )
            }
          >
            <Icon size={18} className="shrink-0" />
            {!sidebarCollapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-panel-border p-3 space-y-2">
        {!sidebarCollapsed && (
          <div className="px-2 py-1 text-xs text-panel-muted truncate">
            Signed in as <span className="text-white font-medium">{username}</span>
          </div>
        )}
        <button
          onClick={() => clearAuth()}
          className={clsx(
            'flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm',
            'text-gray-400 hover:bg-danger/10 hover:text-danger transition-colors'
          )}
        >
          <LogOut size={18} className="shrink-0" />
          {!sidebarCollapsed && <span>Sign Out</span>}
        </button>
        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center w-full py-1 text-panel-muted hover:text-white transition-colors"
        >
          {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  )
}

