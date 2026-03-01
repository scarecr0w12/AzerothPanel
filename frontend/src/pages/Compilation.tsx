import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Hammer, StopCircle, RotateCcw, GitPullRequest, ArrowUpCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { compileApi, modulesApi } from '@/services/api'
import { Card, CardHeader } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import type { BuildStatus } from '@/types'

const BUILD_TYPES = ['Release', 'RelWithDebInfo', 'Debug']

const CMAKE_FLAGS = [
  { key: 'TOOLS',         cmake: '-DTOOLS_BUILD=all',  label: 'Build Tools',    default: true  },
  { key: 'SCRIPTS',       cmake: '-DWITH_SCRIPTS=1',   label: 'Lua Scripts',    default: false },
  { key: 'WITH_WARNINGS', cmake: '-DWITH_WARNINGS=1',  label: 'Verbose Warns',  default: false },
]

export default function Compilation() {
  const [buildType, setBuildType] = useState('RelWithDebInfo')
  const [jobs, setJobs] = useState(4)
  const [flags, setFlags] = useState<Record<string, boolean>>(
    Object.fromEntries(CMAKE_FLAGS.map((f) => [f.key, f.default]))
  )
  const [logs, setLogs] = useState<string[]>([])
  const [building, setBuilding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // ── Source update state
  const [updateLogs, setUpdateLogs] = useState<string[]>([])
  const [updating, setUpdating] = useState(false)
  const [updateDone, setUpdateDone] = useState(false)
  const [updateExpanded, setUpdateExpanded] = useState(false)
  const updateBottomRef = useRef<HTMLDivElement>(null)
  const updateAbortRef = useRef<AbortController | null>(null)

  const statusQuery = useQuery<BuildStatus>({
    queryKey: ['build-status'],
    queryFn: () => compileApi.status().then((r) => r.data),
    refetchInterval: building ? 2000 : false,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    updateBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [updateLogs])

  async function pullSource() {
    setUpdateLogs([])
    setUpdateDone(false)
    setUpdating(true)
    setUpdateExpanded(true)

    const ctrl = new AbortController()
    updateAbortRef.current = ctrl

    try {
      const resp = await modulesApi.updateAzerothCore(ctrl.signal)
      if (!resp.ok) {
        const txt = await resp.text().catch(() => `HTTP ${resp.status}`)
        setUpdateLogs([`[error] ${txt}`])
        setUpdateDone(true)
        return
      }

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n')
        buf = parts.pop() ?? ''
        for (const raw of parts) {
          if (!raw.startsWith('data: ')) continue
          try {
            const payload = JSON.parse(raw.slice(6))
            if (payload.done) { setUpdateDone(true); break }
            if (payload.line) setUpdateLogs((prev) => [...prev, payload.line as string])
          } catch { /* ignore */ }
        }
      }
    } catch (e: unknown) {
      if ((e as { name?: string })?.name !== 'AbortError') {
        setUpdateLogs((prev) => [...prev, `[error] ${String(e)}`])
      }
    } finally {
      setUpdating(false)
      setUpdateDone(true)
    }
  }

  async function startBuild() {
    setLogs([])
    setError(null)
    setBuilding(true)

    // Build cmake_extra from selected flags
    const cmakeExtra = CMAKE_FLAGS
      .filter((f) => flags[f.key])
      .map((f) => f.cmake)
      .join(' ')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await compileApi.build(buildType, jobs, cmakeExtra, controller.signal)
      if (!response.ok) {
        const text = await response.text().catch(() => `HTTP ${response.status}`)
        setError(text)
        setBuilding(false)
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n')
        buffer = parts.pop() ?? ''

        for (const line of parts) {
          if (!line.startsWith('data: ')) continue
          try {
            const payload = JSON.parse(line.slice(6))
            if (payload.line) {
              setLogs((prev) => {
                const next = [...prev, payload.line as string]
                return next.length > 3000 ? next.slice(-3000) : next
              })
            }
            if (payload.done) {
              setBuilding(false)
            }
          } catch { /* ignore malformed SSE */ }
        }
      }
    } catch (err: unknown) {
      if ((err as { name?: string }).name !== 'AbortError') {
        setError(String(err))
      }
    } finally {
      setBuilding(false)
    }
  }

  function cancelBuild() {
    abortRef.current?.abort()
    setBuilding(false)
    setLogs((prev) => [...prev, '--- Build cancelled by user ---'])
  }

  const status = statusQuery.data
  const progress = status?.progress_percent ?? 0

  return (
    <div className="space-y-4">

      {/* ── Source update card */}
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitPullRequest size={16} className="text-brand" />
            <div>
              <h3 className="text-sm font-semibold text-white">Update AzerothCore Source</h3>
              <p className="text-xs text-panel-muted mt-0.5">
                Pull the latest commits from the AzerothCore git repository before building.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              size="sm"
              variant="secondary"
              disabled={updating || building}
              onClick={pullSource}
            >
              {updating
                ? <><RotateCcw size={13} className="animate-spin" /> Pulling…</>
                : <><ArrowUpCircle size={13} /> Pull Latest Source</>}
            </Button>
            {updateLogs.length > 0 && (
              <button
                onClick={() => setUpdateExpanded((v) => !v)}
                className="p-1.5 text-gray-400 hover:text-white transition-colors"
              >
                {updateExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
              </button>
            )}
          </div>
        </div>

        {/* Inline log output */}
        {updateExpanded && updateLogs.length > 0 && (
          <div className="mt-4 rounded-lg bg-panel-bg border border-panel-border max-h-64 overflow-y-auto px-4 py-3">
            {updateLogs.map((line, i) => {
              const isOk  = line.startsWith('[ok]')
              const isErr = line.startsWith('[error]') || line.includes('[exit ')
              const isInf = line.startsWith('[info]') || line.startsWith('[cmd]')
              return (
                <div key={i} className={`font-mono text-xs leading-5 ${
                  isOk  ? 'text-green-400' :
                  isErr ? 'text-red-400' :
                  isInf ? 'text-blue-300' :
                  'text-gray-300'
                }`}>{line}</div>
              )
            })}
            {updating && <div className="text-yellow-400 text-xs animate-pulse mt-1">Running…</div>}
            {updateDone && (
              <div className={`text-xs mt-1 font-medium ${
                updateLogs.some(l => l.startsWith('[ok]')) ? 'text-green-400' : 'text-red-400'
              }`}>
                {updateLogs.some(l => l.startsWith('[ok]')) ? '✔ Complete' : '✘ Finished with errors'}
              </div>
            )}
            <div ref={updateBottomRef} />
          </div>
        )}
      </Card>

      {/* Config card */}
      <Card>
        <CardHeader title="Build Configuration" subtitle="Configure and start a new compilation" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="space-y-3">
            <label className="text-xs font-medium text-panel-muted uppercase tracking-wide">Build Type</label>
            <div className="flex flex-col gap-2">
              {BUILD_TYPES.map((t) => (
                <button key={t} onClick={() => setBuildType(t)} disabled={building}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                    buildType === t ? 'bg-brand text-white' : 'bg-panel-bg border border-panel-border text-panel-muted hover:text-white'
                  }`}>{t}</button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-xs font-medium text-panel-muted uppercase tracking-wide">CMake Flags</label>
            <div className="space-y-2">
              {CMAKE_FLAGS.map((f) => (
                <label key={f.key} className="flex items-center gap-2.5 cursor-pointer">
                  <input type="checkbox" checked={flags[f.key]} disabled={building}
                    onChange={(e) => setFlags((prev) => ({ ...prev, [f.key]: e.target.checked }))}
                    className="w-4 h-4 accent-brand" />
                  <span className="text-sm text-gray-300">{f.label}</span>
                  <code className="text-xs text-panel-muted font-mono">{f.cmake}</code>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-xs font-medium text-panel-muted uppercase tracking-wide">
              Parallel Jobs (make -j)
            </label>
            <input
              type="number" min={1} max={32} value={jobs}
              disabled={building}
              onChange={(e) => setJobs(Math.max(1, parseInt(e.target.value) || 4))}
              className="w-24 bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-brand disabled:opacity-50"
            />
            <p className="text-xs text-panel-muted">Set to your CPU thread count for fastest builds.</p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3 items-center">
          {!building ? (
            <Button icon={<Hammer size={15} />} onClick={startBuild}>Start Build</Button>
          ) : (
            <Button variant="danger" icon={<StopCircle size={15} />} onClick={cancelBuild}>Cancel Build</Button>
          )}
          <Button variant="ghost" size="sm" icon={<RotateCcw size={14} />} onClick={() => setLogs([])}>Clear Output</Button>
        </div>
      </Card>

      {/* Progress bar (shown while building) */}
      {building && (
        <Card>
          <div className="flex items-center justify-between mb-2 text-sm">
            <span className="text-panel-muted">{status?.current_step ?? 'Building…'}</span>
            <span className="font-mono text-brand-light">{progress}%</span>
          </div>
          <div className="w-full h-2 bg-panel-bg rounded-full overflow-hidden">
            <div className="h-full bg-brand rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }} />
          </div>
        </Card>
      )}

      {/* Build output terminal */}
      <Card padding={false} className="flex flex-col">
        <CardHeader title="Build Output" subtitle={`${logs.length} lines`} />
        {error && (
          <div className="mx-5 mb-3 bg-danger/10 border border-danger/30 text-danger text-sm rounded-lg px-4 py-3">
            ✕ {error}
          </div>
        )}
        <div className="h-96 overflow-y-auto bg-panel-bg rounded-b-xl px-4 pb-4">
          {logs.length === 0 && (
            <p className="text-panel-muted text-xs pt-4">No output yet. Start a build to see live output here.</p>
          )}
          {logs.map((line, i) => (
            <div key={i} className={`font-mono text-xs leading-5 ${
              line.includes('error') || line.includes('Error') ? 'text-danger'
              : line.includes('warning') || line.includes('Warning') ? 'text-warning'
              : line.startsWith('---') ? 'text-brand-light'
              : 'text-gray-300'
            }`}>{line}</div>
          ))}
          <div ref={bottomRef} />
        </div>
      </Card>
    </div>
  )
}

