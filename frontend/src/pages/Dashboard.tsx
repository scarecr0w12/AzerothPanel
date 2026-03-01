import { Link } from 'react-router-dom'
import { Users, Server, Activity, HardDrive, Terminal, ScrollText, Play } from 'lucide-react'
import { useServerStatus } from '@/hooks/useServerStatus'
import { StatCard, Card, CardHeader } from '@/components/ui/Card'
import StatusBadge from '@/components/ui/StatusBadge'

function formatUptime(seconds?: number): string {
  if (!seconds) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

const QUICK_ACTIONS = [
  { to: '/server',   icon: Play,       label: 'Server Control', desc: 'Start, stop or restart servers' },
  { to: '/logs',     icon: ScrollText, label: 'Logs',           desc: 'Live worldserver & auth logs' },
  { to: '/players',  icon: Users,      label: 'Players',        desc: 'Online characters & accounts' },
  { to: '/configs',  icon: Terminal,   label: 'Config Files',   desc: 'Edit .conf files in the browser' },
]

export default function Dashboard() {
  const { data: status, isLoading } = useServerStatus()

  const world = status?.worldserver
  const auth = status?.authserver

  return (
    <div className="space-y-6">
      {/* Stat cards row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Worldserver"
          value={isLoading ? '…' : (world?.running ? 'Online' : 'Offline')}
          sub={world?.running ? `Uptime ${formatUptime(world.uptime_seconds)}` : 'Process stopped'}
          icon={<Server size={18} />}
        />
        <StatCard
          label="Authserver"
          value={isLoading ? '…' : (auth?.running ? 'Online' : 'Offline')}
          sub={auth?.running ? `Uptime ${formatUptime(auth.uptime_seconds)}` : 'Process stopped'}
          icon={<Activity size={18} />}
        />
        <StatCard
          label="CPU Usage"
          value={world?.running ? `${world.cpu_percent ?? 0}%` : '—'}
          sub="worldserver process"
          icon={<HardDrive size={18} />}
        />
        <StatCard
          label="Memory Usage"
          value={world?.running ? `${Math.round(world.memory_mb ?? 0)} MB` : '—'}
          sub="worldserver RSS"
          icon={<Users size={18} />}
        />
      </div>

      {/* Process detail cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ProcessCard label="Worldserver" proc={world} loading={isLoading} />
        <ProcessCard label="Authserver" proc={auth} loading={isLoading} />
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-sm font-semibold text-panel-muted uppercase tracking-wider mb-3">Quick Actions</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {QUICK_ACTIONS.map(({ to, icon: Icon, label, desc }) => (
            <Link
              key={to}
              to={to}
              className="flex items-start gap-3 p-4 rounded-xl bg-panel-surface border border-panel-border
                         hover:border-brand/50 hover:bg-panel-hover transition-colors group"
            >
              <div className="p-2 rounded-lg bg-brand/10 group-hover:bg-brand/20 transition-colors shrink-0">
                <Icon size={16} className="text-brand" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{label}</p>
                <p className="text-xs text-panel-muted mt-0.5 leading-snug">{desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}

function ProcessCard({
  label,
  proc,
  loading,
}: {
  label: string
  proc?: { running: boolean; pid?: number; uptime_seconds?: number; cpu_percent?: number; memory_mb?: number }
  loading: boolean
}) {
  return (
    <Card>
      <CardHeader
        title={label}
        action={
          <StatusBadge
            status={loading ? 'starting' : proc?.running ? 'online' : 'offline'}
          />
        }
      />
      <dl className="grid grid-cols-2 gap-3 text-sm">
        {[
          ['PID',    proc?.running ? proc?.pid : '—'],
          ['Uptime', formatUptime(proc?.uptime_seconds)],
          ['CPU',    proc?.running ? `${proc?.cpu_percent ?? 0}%` : '—'],
          ['Memory', proc?.running ? `${Math.round(proc?.memory_mb ?? 0)} MB` : '—'],
        ].map(([k, v]) => (
          <div key={k as string}>
            <dt className="text-panel-muted text-xs">{k}</dt>
            <dd className="text-white font-mono font-medium mt-0.5">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

