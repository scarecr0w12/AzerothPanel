import { useState } from 'react'
import { Play, Square, RotateCcw, Terminal } from 'lucide-react'
import { useServerStatus, useStartWorld, useStopWorld, useRestartWorld,
         useStartAuth, useStopAuth, useRestartAuth } from '@/hooks/useServerStatus'
import { serverApi } from '@/services/api'
import { Card, CardHeader } from '@/components/ui/Card'
import StatusBadge from '@/components/ui/StatusBadge'
import Button from '@/components/ui/Button'

function ServerCard({
  label, running, loading,
  onStart, onStop, onRestart,
  startLoading, stopLoading, restartLoading,
  pid, uptime, cpu, mem,
}: {
  label: string; running?: boolean; loading: boolean
  onStart: () => void; onStop: () => void; onRestart: () => void
  startLoading: boolean; stopLoading: boolean; restartLoading: boolean
  pid?: number; uptime?: number; cpu?: number; mem?: number
}) {
  const fmt = (s?: number) => {
    if (!s) return '—'
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
    return h > 0 ? `${h}h ${m}m` : `${m}m`
  }

  return (
    <Card>
      <CardHeader
        title={label}
        action={<StatusBadge status={loading ? 'starting' : running ? 'online' : 'offline'} />}
      />
      <dl className="grid grid-cols-2 gap-3 text-sm mb-5">
        {[['PID', pid ?? '—'], ['Uptime', fmt(uptime)], ['CPU', running ? `${cpu ?? 0}%` : '—'], ['Memory', running ? `${Math.round(mem ?? 0)} MB` : '—']].map(([k, v]) => (
          <div key={k as string}>
            <dt className="text-xs text-panel-muted">{k}</dt>
            <dd className="text-white font-mono font-medium mt-0.5">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button variant="success" size="sm" icon={<Play size={13} />}
          loading={startLoading} disabled={running} onClick={onStart}>Start</Button>
        <Button variant="danger" size="sm" icon={<Square size={13} />}
          loading={stopLoading} disabled={!running} onClick={onStop}>Stop</Button>
        <Button variant="secondary" size="sm" icon={<RotateCcw size={13} />}
          loading={restartLoading} onClick={onRestart}>Restart</Button>
      </div>
    </Card>
  )
}

export default function ServerControl() {
  const { data: status, isLoading } = useServerStatus(3000)
  const startWorld = useStartWorld()
  const stopWorld = useStopWorld()
  const restartWorld = useRestartWorld()
  const startAuth = useStartAuth()
  const stopAuth = useStopAuth()
  const restartAuth = useRestartAuth()

  const [cmd, setCmd] = useState('')
  const [cmdResult, setCmdResult] = useState<string | null>(null)
  const [cmdLoading, setCmdLoading] = useState(false)

  async function sendCommand() {
    if (!cmd.trim()) return
    setCmdLoading(true)
    try {
      const { data } = await serverApi.command(cmd)
      setCmdResult(data.result)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setCmdResult('Error: ' + (err.response?.data?.detail ?? 'Unknown error'))
    } finally {
      setCmdLoading(false)
    }
  }

  const w = status?.worldserver
  const a = status?.authserver

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ServerCard label="Worldserver" running={w?.running} loading={isLoading}
          pid={w?.pid} uptime={w?.uptime_seconds} cpu={w?.cpu_percent} mem={w?.memory_mb}
          onStart={() => startWorld.mutate()} startLoading={startWorld.isPending}
          onStop={() => stopWorld.mutate()} stopLoading={stopWorld.isPending}
          onRestart={() => restartWorld.mutate()} restartLoading={restartWorld.isPending} />
        <ServerCard label="Authserver" running={a?.running} loading={isLoading}
          pid={a?.pid} uptime={a?.uptime_seconds} cpu={a?.cpu_percent} mem={a?.memory_mb}
          onStart={() => startAuth.mutate()} startLoading={startAuth.isPending}
          onStop={() => stopAuth.mutate()} stopLoading={stopAuth.isPending}
          onRestart={() => restartAuth.mutate()} restartLoading={restartAuth.isPending} />
      </div>

      {/* GM Console */}
      <Card>
        <CardHeader title="GM Console" subtitle="Send commands directly to the worldserver console" />
        <div className="flex gap-2">
          <div className="flex-1 flex items-center gap-2 bg-panel-bg border border-panel-border rounded-lg px-3">
            <Terminal size={14} className="text-panel-muted shrink-0" />
            <input
              value={cmd} onChange={(e) => setCmd(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendCommand()}
              placeholder=".server info"
              className="flex-1 bg-transparent py-2 text-sm text-white placeholder-panel-muted outline-none font-mono"
            />
          </div>
          <Button onClick={sendCommand} loading={cmdLoading} disabled={!cmd.trim()}>
            Execute
          </Button>
        </div>
        {cmdResult && (
          <pre className="mt-3 bg-panel-bg border border-panel-border rounded-lg p-3 text-xs font-mono text-green-400 whitespace-pre-wrap max-h-48 overflow-y-auto">
            {cmdResult}
          </pre>
        )}
      </Card>
    </div>
  )
}

