import { Users, Server, Activity, HardDrive } from 'lucide-react'
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

export default function Dashboard() {
  const { data: status, isLoading } = useServerStatus()

  const world = status?.worldserver
  const auth = status?.authserver

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Overview</h2>
        <p className="text-sm text-panel-muted mt-1">Real-time status of your AzerothCore server</p>
      </div>

      {/* Stat cards row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Worldserver"
          value={isLoading ? '…' : (world?.running ? 'Online' : 'Offline')}
          sub={world?.running ? `Uptime ${formatUptime(world.uptime_seconds)}` : 'Stopped'}
          icon={<Server size={18} />}
        />
        <StatCard
          label="Authserver"
          value={isLoading ? '…' : (auth?.running ? 'Online' : 'Offline')}
          sub={auth?.running ? `Uptime ${formatUptime(auth.uptime_seconds)}` : 'Stopped'}
          icon={<Activity size={18} />}
        />
        <StatCard
          label="CPU (World)"
          value={world?.running ? `${world.cpu_percent ?? 0}%` : '—'}
          sub="worldserver process"
          icon={<HardDrive size={18} />}
        />
        <StatCard
          label="Memory (World)"
          value={world?.running ? `${Math.round(world.memory_mb ?? 0)} MB` : '—'}
          sub="worldserver RSS"
          icon={<Users size={18} />}
        />
      </div>

      {/* Process cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ProcessCard label="Worldserver" proc={world} loading={isLoading} />
        <ProcessCard label="Authserver" proc={auth} loading={isLoading} />
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

