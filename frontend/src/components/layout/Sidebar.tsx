import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Server, ScrollText, Users, Database,
  Download, Hammer, LogOut, ChevronLeft, ChevronRight, Shield, Settings,
  HardDrive, Package, FileText,
} from 'lucide-react'
import clsx from 'clsx'
import { useUIStore, useAuthStore } from '@/store'
import type { LucideIcon } from 'lucide-react'

interface NavItem {
  to: string
  icon: LucideIcon
  label: string
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Monitor',
    items: [
      { to: '/',     icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/logs', icon: ScrollText,      label: 'Logs' },
    ],
  },
  {
    label: 'Manage',
    items: [
      { to: '/server',   icon: Server,   label: 'Server Control' },
      { to: '/players',  icon: Users,    label: 'Players' },
      { to: '/database', icon: Database, label: 'Database' },
    ],
  },
  {
    label: 'Build & Deploy',
    items: [
      { to: '/installation',    icon: Download,  label: 'Installation' },
      { to: '/compilation',     icon: Hammer,    label: 'Compilation' },
      { to: '/data-extraction', icon: HardDrive, label: 'Data Extraction' },
      { to: '/modules',         icon: Package,   label: 'Modules' },
    ],
  },
  {
    label: 'Configure',
    items: [
      { to: '/configs',  icon: FileText, label: 'Config Files' },
      { to: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
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
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {/* Group label — hidden when collapsed */}
            {!sidebarCollapsed && (
              <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-panel-muted">
                {group.label}
              </p>
            )}
            {sidebarCollapsed && (
              <div className="mx-3 my-1 h-px bg-panel-border" />
            )}
            <div className="space-y-0.5">
              {group.items.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium',
                      'transition-colors duration-150',
                      isActive
                        ? 'bg-brand/20 text-brand-light'
                        : 'text-gray-400 hover:bg-panel-hover hover:text-white'
                    )
                  }
                  title={sidebarCollapsed ? label : undefined}
                >
                  <Icon size={17} className="shrink-0" />
                  {!sidebarCollapsed && <span>{label}</span>}
                </NavLink>
              ))}
            </div>
          </div>
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
          title={sidebarCollapsed ? 'Sign Out' : undefined}
        >
          <LogOut size={17} className="shrink-0" />
          {!sidebarCollapsed && <span>Sign Out</span>}
        </button>
        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center w-full py-1 text-panel-muted hover:text-white transition-colors"
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  )
}

