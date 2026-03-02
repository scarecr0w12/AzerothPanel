import { useEffect, useRef, useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, Wifi, WifiOff, Search, Filter, Trash2 } from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { logsApi, instancesApi } from '@/services/api'
import { Card, CardHeader } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import type { LogSource, WorldServerInstance } from '@/types'

const SOURCES: { value: LogSource; label: string }[] = [
  { value: 'worldserver', label: 'Worldserver' },
  { value: 'authserver',  label: 'Authserver' },
  { value: 'gm',          label: 'GM Commands' },
  { value: 'db_errors',   label: 'DB Errors' },
]
const LEVELS = ['ALL', 'ERROR', 'WARN', 'INFO', 'DEBUG']

const LEVEL_COLOR: Record<string, string> = {
  ERROR: 'text-danger', FATAL: 'text-danger', WARN: 'text-warning',
  WARNING: 'text-warning', INFO: 'text-blue-400', DEBUG: 'text-panel-muted',
  TRACE: 'text-panel-muted',
}

export default function LogViewer() {
  const [source, setSource] = useState<LogSource>('worldserver')
  const [levelFilter, setLevelFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [lines, setLines] = useState<string[]>([])  
  const [liveMode, setLiveMode] = useState(true)
  const [selectedInstanceId, setSelectedInstanceId] = useState<number | undefined>()
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const instancesQuery = useQuery({
    queryKey: ['worldserver-instances'],
    queryFn: () => instancesApi.list().then((r) => r.data.instances as WorldServerInstance[]),
    staleTime: 30_000,
  })
  const instances = instancesQuery.data ?? []

  // Build WebSocket path, embedding instance_id in query string when set
  // so useWebSocket appends &token=... rather than ?token=...
  const wsPath = selectedInstanceId != null
    ? `/ws/logs/${source}?instance_id=${selectedInstanceId}`
    : `/ws/logs/${source}`

  // Buffer for incoming WS lines – flushed to state on each animation frame
  // so bursts of many lines cause a single re-render, not one per line.
  const pendingRef = useRef<string[]>([])
  const rafRef = useRef<number | null>(null)

  const flushPending = useCallback(() => {
    rafRef.current = null
    if (pendingRef.current.length === 0) return
    const batch = pendingRef.current
    pendingRef.current = []
    setLines((prev) => {
      const next = [...prev, ...batch]
      return next.length > 2000 ? next.slice(-2000) : next
    })
  }, [])

  const addLine = useCallback((line: string) => {
    pendingRef.current.push(line)
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(flushPending)
    }
  }, [flushPending])

  // Cancel any pending raf on unmount
  useEffect(() => () => { if (rafRef.current !== null) cancelAnimationFrame(rafRef.current) }, [])

  const { connected, send } = useWebSocket(wsPath, {
    onMessage: (raw) => {
      try {
        const { line } = JSON.parse(raw)
        addLine(line)
      } catch {
        addLine(raw)
      }
    },
    autoReconnect: true,
  })

  // Send level filter update to server when it changes
  useEffect(() => {
    send({ level: levelFilter === 'ALL' ? null : levelFilter })
  }, [levelFilter, send])

  // Auto-scroll – use 'instant' so rapid batched updates don't fight each other
  useEffect(() => {
    if (liveMode) bottomRef.current?.scrollIntoView({ behavior: 'instant' })
  }, [lines, liveMode])

  // Load historical lines when source or instance changes.
  useEffect(() => {
    setLines([])
    logsApi.tail(source, 300, selectedInstanceId).then(({ data }) => {
      const historical = data.entries.map((e: { message: string }) => e.message)
      setLines((prev) => [...historical, ...prev])
    }).catch(() => {})
  }, [source, selectedInstanceId])

  const filtered = search
    ? lines.filter((l) => l.toLowerCase().includes(search.toLowerCase()))
    : lines

  function getLevel(line: string) {
    const upper = line.toUpperCase()
    for (const lvl of ['FATAL', 'ERROR', 'WARN', 'INFO', 'DEBUG', 'TRACE']) {
      if (upper.includes(lvl)) return lvl
    }
    return 'INFO'
  }

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Controls */}
      <Card padding={false}>
        <div className="flex flex-wrap items-center gap-3 p-3">
          {/* Source selector */}
          <div className="flex gap-1">
            {SOURCES.map((s) => (
              <button key={s.value} onClick={() => setSource(s.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  source === s.value ? 'bg-brand text-white' : 'bg-panel-bg text-panel-muted hover:text-white'
                }`}>{s.label}</button>
            ))}
          </div>
          {/* Instance selector (shown when more than one instance exists) */}
          {instances.length > 1 && (
            <select
              value={selectedInstanceId ?? ''}
              onChange={e => {
                setSelectedInstanceId(e.target.value === '' ? undefined : Number(e.target.value))
                setLines([])
              }}
              className="bg-panel-bg border border-panel-border rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-brand"
            >
              <option value="">Global (default)</option>
              {instances.map(i => (
                <option key={i.id} value={i.id}>{i.display_name}</option>
              ))}
            </select>
          )}
          <div className="h-4 border-l border-panel-border" />
          {/* Level filter */}
          <div className="flex gap-1">
            <Filter size={14} className="self-center text-panel-muted" />
            {LEVELS.map((l) => (
              <button key={l} onClick={() => setLevelFilter(l)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  levelFilter === l ? 'bg-brand/20 text-brand-light' : 'text-panel-muted hover:text-white'
                }`}>{l}</button>
            ))}
          </div>
          <div className="flex-1 flex items-center gap-2 bg-panel-bg border border-panel-border rounded-lg px-2.5 py-1.5 min-w-36">
            <Search size={13} className="text-panel-muted shrink-0" />
            <input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Search logs…"
              className="bg-transparent text-xs text-white placeholder-panel-muted outline-none flex-1" />
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <span className={`flex items-center gap-1.5 text-xs ${connected ? 'text-success' : 'text-danger'}`}>
              {connected ? <Wifi size={13} /> : <WifiOff size={13} />}
              {connected ? 'Live' : 'Disconnected'}
            </span>
            <Button variant="ghost" size="sm" icon={<Trash2 size={13} />}
              onClick={() => setLines([])}>Clear</Button>
            <Button variant="secondary" size="sm" icon={<Download size={13} />}
              onClick={() => window.open(logsApi.download(source, selectedInstanceId))}>Download</Button>
          </div>
        </div>
      </Card>

      {/* Log terminal */}
      <Card padding={false} className="flex-1 overflow-hidden">
        <CardHeader title={`${source} – ${filtered.length} lines`}
          action={
            <button onClick={() => setLiveMode((v) => !v)}
              className={`text-xs px-2 py-1 rounded ${liveMode ? 'bg-success/10 text-success' : 'bg-panel-hover text-panel-muted'}`}>
              {liveMode ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
            </button>
          }
        />
        <div ref={containerRef} className="h-[calc(100%-3rem)] overflow-y-auto px-4 pb-4">
          {filtered.map((line, i) => {
            const lvl = getLevel(line)
            return (
              <div key={i} className={`font-mono text-xs leading-5 ${LEVEL_COLOR[lvl] ?? 'text-gray-300'}`}>
                {line}
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>
      </Card>
    </div>
  )
}

