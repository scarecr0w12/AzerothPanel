import { useEffect, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Package, Download, Trash2, Star, GitFork, Search, RefreshCw,
  CheckCircle2, XCircle, ExternalLink, ChevronLeft, ChevronRight,
  AlertTriangle, Terminal, X, Layers, Gauge, ArrowUpCircle, GitPullRequest,
} from 'lucide-react'
import { modulesApi } from '@/services/api'
import { Card } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import type { CatalogueModule, CatalogueResponse, InstalledModule } from '@/types'

// ─── Constants ────────────────────────────────────────────────────────────────

const CATEGORIES = [
  { value: 'modules',  label: 'Modules' },
  { value: 'premium',  label: 'Premium' },
  { value: 'tools',    label: 'Tools' },
  { value: 'lua',      label: 'Lua Scripts' },
  { value: 'sql',      label: 'SQL Scripts' },
]

// ─── Sub components ───────────────────────────────────────────────────────────

function LogPanel({
  logs,
  done,
  onClose,
  title,
}: {
  logs: string[]
  done: boolean
  onClose: () => void
  title: string
}) {
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const success = done && logs.some((l) => l.includes('[ok]'))
  const failed  = done && logs.some((l) => l.includes('[error]') || l.includes('[exit '))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-3xl bg-panel-surface border border-panel-border rounded-xl flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-panel-border">
          <div className="flex items-center gap-2">
            <Terminal size={16} className="text-brand" />
            <span className="font-medium text-white text-sm">{title}</span>
          </div>
          <div className="flex items-center gap-2">
            {done && success && (
              <span className="flex items-center gap-1 text-green-400 text-xs font-medium">
                <CheckCircle2 size={14} /> Complete
              </span>
            )}
            {done && failed && (
              <span className="flex items-center gap-1 text-red-400 text-xs font-medium">
                <XCircle size={14} /> Error
              </span>
            )}
            {!done && (
              <span className="text-yellow-400 text-xs animate-pulse">Running…</span>
            )}
            {done && (
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-white transition-colors ml-2"
              >
                <X size={18} />
              </button>
            )}
          </div>
        </div>

        {/* Log output */}
        <div className="flex-1 overflow-y-auto p-4 font-mono text-xs text-gray-300 space-y-0.5 bg-panel-bg rounded-b-xl">
          {logs.map((line, i) => {
            const isOk    = line.startsWith('[ok]')
            const isErr   = line.startsWith('[error]') || line.includes('[exit ')
            const isInfo  = line.startsWith('[info]') || line.startsWith('[cmd]')
            return (
              <div
                key={i}
                className={
                  isOk  ? 'text-green-400' :
                  isErr ? 'text-red-400' :
                  isInfo? 'text-blue-300' :
                  'text-gray-300'
                }
              >
                {line}
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}

// ─── Module card ──────────────────────────────────────────────────────────────

function ModuleCard({
  mod,
  onInstall,
  installing,
}: {
  mod: CatalogueModule
  onInstall: (mod: CatalogueModule) => void
  installing: boolean
}) {
  return (
    <div
      className="bg-panel-surface border border-panel-border rounded-xl p-5 flex flex-col gap-3
                 hover:border-brand/40 transition-colors"
    >
      {/* Top row */}
      <div className="flex items-start gap-3">
        <img
          src={mod.owner_avatar}
          alt={mod.owner_login}
          className="w-10 h-10 rounded-full border border-panel-border shrink-0"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <a
              href={mod.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-white hover:text-brand-light transition-colors text-sm flex items-center gap-1"
            >
              {mod.name}
              <ExternalLink size={11} className="opacity-60 shrink-0" />
            </a>
            {mod.archived && (
              <span className="text-xs bg-yellow-900/40 text-yellow-400 px-1.5 py-0.5 rounded">
                archived
              </span>
            )}
            {mod.installed && (
              <span className="text-xs bg-green-900/40 text-green-400 px-1.5 py-0.5 rounded flex items-center gap-1">
                <CheckCircle2 size={10} /> installed
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-0.5 truncate">{mod.owner_login}/{mod.name}</p>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-300 line-clamp-2 min-h-[2.5rem]">
        {mod.description || <span className="italic text-gray-500">No description.</span>}
      </p>

      {/* Meta row */}
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <span className="flex items-center gap-1">
          <Star size={12} className="text-yellow-400" />
          {mod.stars.toLocaleString()}
        </span>
        <span className="flex items-center gap-1">
          <GitFork size={12} />
          {mod.forks.toLocaleString()}
        </span>
        {mod.updated_at && (
          <span>Updated {new Date(mod.updated_at).toLocaleDateString()}</span>
        )}
      </div>

      {/* Action */}
      <Button
        size="sm"
        variant={mod.installed ? 'ghost' : 'primary'}
        disabled={mod.installed || installing}
        onClick={() => onInstall(mod)}
        className="w-full mt-auto"
      >
        {installing ? (
          <><RefreshCw size={13} className="animate-spin" /> Installing…</>
        ) : mod.installed ? (
          <><CheckCircle2 size={13} /> Already Installed</>
        ) : (
          <><Download size={13} /> Install</>
        )}
      </Button>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

type Tab = 'catalogue' | 'installed'

export default function ModuleManager() {
  const qc = useQueryClient()

  // ── Tab / catalogue state
  const [tab, setTab] = useState<Tab>('catalogue')
  const [category, setCategory] = useState('modules')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const PER_PAGE = 30

  // ── Install log state
  const [installLogs, setInstallLogs] = useState<string[]>([])
  const [installDone, setInstallDone] = useState(false)
  const [installTarget, setInstallTarget] = useState<CatalogueModule | null>(null)
  const [installingName, setInstallingName] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // ── Update log state
  const [updateLogs, setUpdateLogs] = useState<string[]>([])
  const [updateDone, setUpdateDone] = useState(false)
  const [updateTitle, setUpdateTitle] = useState('')
  const [updatingName, setUpdatingName] = useState<string | null>(null) // module name, 'azerothcore', 'all'
  const updateAbortRef = useRef<AbortController | null>(null)

  // ── Remove state
  const [removeError, setRemoveError] = useState<string | null>(null)

  // ── Catalogue query
  const catalogueQuery = useQuery<CatalogueResponse>({
    queryKey: ['modules-catalogue', category, page],
    queryFn: () => modulesApi.catalogue(category, page, PER_PAGE).then((r) => r.data),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })

  // ── Installed query
  const installedQuery = useQuery<{ modules_path: string; modules: InstalledModule[] }>({
    queryKey: ['modules-installed'],
    queryFn: () => modulesApi.installed().then((r) => r.data),
  })

  // ── Rate-limit query (background, used for status badge)
  type RateLimit = { limit: number; remaining: number; reset_epoch: number; authenticated: boolean }
  const rateLimitQuery = useQuery<RateLimit>({
    queryKey: ['github-rate-limit'],
    queryFn: () => modulesApi.rateLimit().then((r) => r.data),
    staleTime: 60_000,
    retry: false,
  })

  // ── Remove mutation
  const removeMutation = useMutation({
    mutationFn: (name: string) => modulesApi.remove(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['modules-installed'] })
      qc.invalidateQueries({ queryKey: ['modules-catalogue'] })
      setRemoveError(null)
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Remove failed'
      setRemoveError(msg)
    },
  })

  // ── Filtered items (client-side search on already-fetched page)
  const items = catalogueQuery.data?.items ?? []
  const filtered = search.trim()
    ? items.filter(
        (m) =>
          m.name.toLowerCase().includes(search.toLowerCase()) ||
          m.description.toLowerCase().includes(search.toLowerCase()),
      )
    : items

  // ── Install handler
  const handleInstall = useCallback(async (mod: CatalogueModule) => {
    setInstallLogs([])
    setInstallDone(false)
    setInstallTarget(mod)
    setInstallingName(mod.name)

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const resp = await modulesApi.install(mod.clone_url, mod.name, undefined, ctrl.signal)
      if (!resp.ok) {
        const txt = await resp.text().catch(() => `HTTP ${resp.status}`)
        setInstallLogs([`[error] ${txt}`])
        setInstallDone(true)
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
            if (payload.done) {
              setInstallDone(true)
              break
            }
            if (payload.line) {
              setInstallLogs((prev) => [...prev, payload.line as string])
              if (payload.line === '[done]') setInstallDone(true)
            }
          } catch { /* ignore bad json */ }
        }
      }
    } catch (e: unknown) {
      if ((e as { name?: string })?.name !== 'AbortError') {
        setInstallLogs((prev) => [...prev, `[error] ${String(e)}`])
      }
    } finally {
      setInstallDone(true)
      setInstallingName(null)
    }
  }, [])

  // ── Generic update handler (AC source, single module, all modules)
  const handleUpdate = useCallback(async (
    key: string,
    title: string,
    fetchFn: (signal: AbortSignal) => Promise<Response>,
  ) => {
    setUpdateLogs([])
    setUpdateDone(false)
    setUpdateTitle(title)
    setUpdatingName(key)

    const ctrl = new AbortController()
    updateAbortRef.current = ctrl

    try {
      const resp = await fetchFn(ctrl.signal)
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
            if (payload.line) {
              setUpdateLogs((prev) => [...prev, payload.line as string])
              if (payload.line === '[done]') setUpdateDone(true)
            }
          } catch { /* ignore bad json */ }
        }
      }
    } catch (e: unknown) {
      if ((e as { name?: string })?.name !== 'AbortError') {
        setUpdateLogs((prev) => [...prev, `[error] ${String(e)}`])
      }
    } finally {
      setUpdateDone(true)
      setUpdatingName(null)
    }
  }, [])

  // Refresh installed + catalogue after modal close
  const handleLogClose = useCallback(() => {
    setInstallTarget(null)
    setInstallLogs([])
    qc.invalidateQueries({ queryKey: ['modules-installed'] })
    qc.invalidateQueries({ queryKey: ['modules-catalogue'] })
  }, [qc])

  const totalPages = Math.ceil((catalogueQuery.data?.total_count ?? 0) / PER_PAGE)

  return (
    <div className="space-y-6">
      {/* Install log modal */}
      {installTarget && (
        <LogPanel
          logs={installLogs}
          done={installDone}
          onClose={handleLogClose}
          title={`Installing: ${installTarget.name}`}
        />
      )}

      {/* Update log modal */}
      {(updatingName !== null || updateLogs.length > 0) && (
        <LogPanel
          logs={updateLogs}
          done={updateDone}
          onClose={() => {
            setUpdateLogs([])
            setUpdateDone(false)
            setUpdateTitle('')
            qc.invalidateQueries({ queryKey: ['modules-installed'] })
          }}
          title={updateTitle}
        />
      )}

      {/* Rate-limit badge + recompile notice */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {rateLimitQuery.data && (
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border ${
              rateLimitQuery.data.remaining === 0
                ? 'bg-red-900/20 border-red-700/40 text-red-400'
                : rateLimitQuery.data.remaining < 5
                ? 'bg-yellow-900/20 border-yellow-600/40 text-yellow-300'
                : 'bg-panel-surface border-panel-border text-gray-400'
            }`}
          >
            <Gauge size={13} />
            <span>
              GitHub API: {rateLimitQuery.data.remaining}/{rateLimitQuery.data.limit}
              {rateLimitQuery.data.authenticated
                ? ' (authenticated)'
                : <> — <Link to="/settings" className="underline hover:text-white">add token</Link></>}
            </span>
          </div>
        )}
        <p className="text-xs text-panel-muted">
          After installing or removing modules, go to{' '}
          <Link to="/compilation" className="text-brand-light hover:underline">Compilation</Link>{' '}
          to rebuild the server.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-panel-border">
        {(['catalogue', 'installed'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors capitalize ${
              tab === t
                ? 'border-brand text-brand-light'
                : 'border-transparent text-gray-400 hover:text-white'
            }`}
          >
            {t === 'installed'
              ? `Installed (${installedQuery.data?.modules.length ?? '…'})`
              : 'Browse Catalogue'}
          </button>
        ))}
      </div>

      {/* ══ CATALOGUE TAB ══════════════════════════════════════════════════ */}
      {tab === 'catalogue' && (
        <div className="space-y-4">
          {/* Filters */}
          <Card>
            <div className="flex flex-wrap items-center gap-3 p-4">
              {/* Category */}
              <div className="flex gap-1">
                {CATEGORIES.map((c) => (
                  <button
                    key={c.value}
                    onClick={() => { setCategory(c.value); setPage(1); setSearch('') }}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      category === c.value
                        ? 'bg-brand/20 text-brand-light border border-brand/40'
                        : 'text-gray-400 hover:text-white hover:bg-panel-hover'
                    }`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>

              {/* Search */}
              <div className="flex-1 min-w-[200px] relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter by name or description…"
                  className="w-full bg-panel-bg border border-panel-border rounded-lg pl-8 pr-4 py-1.5
                             text-sm text-white placeholder-gray-500 focus:outline-none focus:border-brand/60"
                />
              </div>

              <button
                onClick={() => catalogueQuery.refetch()}
                className="p-2 text-gray-400 hover:text-white transition-colors"
                title="Refresh catalogue"
              >
                <RefreshCw size={15} className={catalogueQuery.isFetching ? 'animate-spin' : ''} />
              </button>
            </div>
          </Card>

          {/* Error */}
          {catalogueQuery.isError && (() => {
            const err = catalogueQuery.error as { response?: { status?: number; data?: { detail?: string } } }
            const status = err?.response?.status
            const detail = err?.response?.data?.detail ?? ''
            const isRateLimit = status === 429 || detail.toLowerCase().includes('rate limit')
            return isRateLimit ? (
              <div className="flex items-start gap-3 bg-yellow-900/20 border border-yellow-600/40 rounded-xl px-4 py-4 text-yellow-300 text-sm">
                <AlertTriangle size={18} className="shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">GitHub API rate limit exceeded</p>
                  <p className="mt-1 text-yellow-200/80 text-xs">
                    Unauthenticated API requests are limited to 10 searches/minute.
                    Add a GitHub Personal Access Token in{' '}
                    <Link to="/settings" className="underline hover:text-white">Settings</Link>{' '}
                    to increase the limit to 30/minute.
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 bg-red-900/20 border border-red-700/40 rounded-lg px-4 py-3 text-red-400 text-sm">
                <AlertTriangle size={16} />
                {detail || 'Failed to fetch catalogue. Check your internet connection.'}
              </div>
            )
          })()}

          {/* Results count */}
          {catalogueQuery.data && (
            <p className="text-xs text-panel-muted">
              Showing {filtered.length} of {catalogueQuery.data.total_count.toLocaleString()} results
              {search && ` matching "${search}"`}
            </p>
          )}

          {/* Grid */}
          {catalogueQuery.isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="bg-panel-surface border border-panel-border rounded-xl p-5 space-y-3 animate-pulse">
                  <div className="flex gap-3">
                    <div className="w-10 h-10 rounded-full bg-panel-border" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-3 bg-panel-border rounded w-1/2" />
                      <div className="h-2 bg-panel-border rounded w-1/3" />
                    </div>
                  </div>
                  <div className="h-2 bg-panel-border rounded" />
                  <div className="h-2 bg-panel-border rounded w-3/4" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((mod) => (
                <ModuleCard
                  key={mod.id}
                  mod={mod}
                  onInstall={handleInstall}
                  installing={installingName === mod.name}
                />
              ))}
              {filtered.length === 0 && !catalogueQuery.isLoading && (
                <div className="col-span-3 text-center py-16 text-panel-muted">
                  <Package size={40} className="mx-auto mb-4 opacity-30" />
                  No modules found.
                </div>
              )}
            </div>
          )}

          {/* Pagination */}
          {!search && totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button
                size="sm"
                variant="ghost"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft size={14} /> Prev
              </Button>
              <span className="text-sm text-gray-400">
                Page {page} / {totalPages}
              </span>
              <Button
                size="sm"
                variant="ghost"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next <ChevronRight size={14} />
              </Button>
            </div>
          )}
        </div>
      )}

      {/* ══ INSTALLED TAB ══════════════════════════════════════════════════ */}
      {tab === 'installed' && (
        <div className="space-y-4">
          {/* ── AzerothCore source update card */}
          <div className="bg-panel-surface border border-panel-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <GitPullRequest size={15} className="text-brand" />
              <h3 className="text-sm font-semibold text-white">AzerothCore Source</h3>
            </div>
            <p className="text-xs text-panel-muted mb-4">
              Pull the latest changes from the AzerothCore git repository.
              After updating you will need to <Link to="/compilation" className="text-brand-light hover:underline">recompile</Link> for changes to take effect.
            </p>
            <Button
              size="sm"
              variant="secondary"
              disabled={updatingName !== null}
              onClick={() =>
                handleUpdate(
                  'azerothcore',
                  'Update AzerothCore Source',
                  (signal) => modulesApi.updateAzerothCore(signal),
                )
              }
            >
              {updatingName === 'azerothcore'
                ? <><RefreshCw size={13} className="animate-spin" /> Updating…</>
                : <><ArrowUpCircle size={13} /> Update AzerothCore Source</>}
            </Button>
          </div>          {/* Path */}
          {installedQuery.data && (
            <p className="text-xs text-panel-muted font-mono bg-panel-surface border border-panel-border rounded-lg px-3 py-2 inline-block">
              Modules directory: {installedQuery.data.modules_path}
            </p>
          )}

          {/* Remove error */}
          {removeError && (
            <div className="flex items-center gap-2 bg-red-900/20 border border-red-700/40 rounded-lg px-4 py-3 text-red-400 text-sm">
              <AlertTriangle size={16} /> {removeError}
            </div>
          )}

          {/* Refresh + Update All */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => installedQuery.refetch()}
            >
              <RefreshCw size={13} className={installedQuery.isFetching ? 'animate-spin' : ''} />
              Refresh
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={updatingName !== null || (installedQuery.data?.modules.filter(m => m.has_git).length ?? 0) === 0}
              onClick={() =>
                handleUpdate(
                  'all',
                  'Update All Modules',
                  (signal) => modulesApi.updateAll(signal),
                )
              }
            >
              {updatingName === 'all'
                ? <><RefreshCw size={13} className="animate-spin" /> Updating…</>
                : <><ArrowUpCircle size={13} /> Update All Modules</>}
            </Button>
          </div>

          {/* List */}
          {installedQuery.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-16 bg-panel-surface border border-panel-border rounded-xl animate-pulse" />
              ))}
            </div>
          ) : (installedQuery.data?.modules.length ?? 0) === 0 ? (
            <div className="text-center py-20 text-panel-muted">
              <Layers size={40} className="mx-auto mb-4 opacity-30" />
              <p>No modules installed yet.</p>
              <p className="text-xs mt-1">Browse the catalogue to install one.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {installedQuery.data!.modules.map((mod) => (
                <div
                  key={mod.name}
                  className="bg-panel-surface border border-panel-border rounded-xl px-5 py-4
                             flex items-center justify-between gap-4 hover:border-brand/20 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="p-2 rounded-lg bg-brand/10">
                      <Package size={16} className="text-brand" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-white text-sm">{mod.name}</p>
                      {mod.remote_url ? (
                        <a
                          href={mod.remote_url.replace(/^git@github\.com:/, 'https://github.com/').replace(/\.git$/, '')}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-panel-muted hover:text-brand-light transition-colors truncate flex items-center gap-1"
                        >
                          {mod.remote_url}
                          <ExternalLink size={9} className="shrink-0" />
                        </a>
                      ) : (
                        <p className="text-xs text-panel-muted font-mono truncate">{mod.path}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    {mod.has_git ? (
                      <span className="text-xs text-green-400 bg-green-900/20 px-2 py-0.5 rounded">git</span>
                    ) : (
                      <span className="text-xs text-gray-500 bg-panel-hover px-2 py-0.5 rounded">no git</span>
                    )}
                    {mod.has_git && (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={updatingName !== null}
                        onClick={() =>
                          handleUpdate(
                            mod.name,
                            `Update: ${mod.name}`,
                            (signal) => modulesApi.updateModule(mod.name, signal),
                          )
                        }
                      >
                        {updatingName === mod.name
                          ? <><RefreshCw size={13} className="animate-spin" /> Updating…</>
                          : <><ArrowUpCircle size={13} /> Update</>}
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => {
                        if (confirm(`Remove module '${mod.name}'? This cannot be undone.`)) {
                          removeMutation.mutate(mod.name)
                        }
                      }}
                      disabled={removeMutation.isPending || updatingName !== null}
                    >
                      <Trash2 size={13} />
                      Remove
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Recompile note */}
          {(installedQuery.data?.modules.length ?? 0) > 0 && (
            <div className="rounded-xl border border-yellow-600/30 bg-yellow-900/10 px-4 py-3 text-yellow-300 text-sm flex items-start gap-2">
              <AlertTriangle size={16} className="shrink-0 mt-0.5" />
              <span>
                After installing or removing modules you must <strong>recompile AzerothCore</strong> for changes to take effect.
                Go to the <strong>Compilation</strong> page to rebuild.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
