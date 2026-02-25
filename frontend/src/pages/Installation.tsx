import { useRef, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { CheckCircle2, XCircle, Save, RefreshCw, Play, StopCircle, RotateCcw } from 'lucide-react'
import { installApi, installStreamApi } from '@/services/api'
import { Card, CardHeader } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import type { InstallCheck } from '@/types'

type ConfigTab = 'worldserver' | 'authserver'

const CHECK_LABELS: Record<keyof InstallCheck, string> = {
  repo_cloned:       'Repository cloned',
  compiled:          'Server compiled',
  authserver_binary: 'Authserver binary present',
  worldserver_conf:  'Worldserver config present',
  authserver_conf:   'Authserver config present',
  data_dir:          'Data directory present',
  log_dir:           'Log directory present',
}

export default function Installation() {
  const [configTab, setConfigTab] = useState<ConfigTab>('worldserver')
  const [editedConf, setEditedConf] = useState<string | null>(null)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)

  // ─── Repository options ─────────────────────────────────────────────────
  const REPO_OPTIONS = [
    {
      value: 'https://github.com/azerothcore/azerothcore-wotlk.git',
      label: 'Standard AzerothCore (Official)',
      description: 'The official AzerothCore repository — recommended for most users.',
    },
    {
      value: 'https://github.com/mod-playerbots/azerothcore-wotlk.git',
      label: 'AzerothCore + Playerbot Module (Fork)',
      description: 'Community fork with the Playerbot module pre-integrated.',
    },
  ] as const

  // ─── Install runner state ───────────────────────────────────────────────
  const [installConfig, setInstallConfig] = useState({
    ac_path: '/opt/azerothcore',
    db_host: '127.0.0.1',
    db_root_password: '',
    db_user: 'acore',
    db_password: 'acore',
    clone_branch: 'master',
    repository_url: 'https://github.com/azerothcore/azerothcore-wotlk.git',
  })
  const [installLogs, setInstallLogs] = useState<string[]>([])
  const [installing, setInstalling] = useState(false)
  const [installError, setInstallError] = useState<string | null>(null)
  const installAbortRef = useRef<AbortController | null>(null)
  const installBottomRef = useRef<HTMLDivElement>(null)

  const checkQuery = useQuery<InstallCheck>({
    queryKey: ['install-status'],
    queryFn: () => installApi.status().then((r) => r.data.checks),
  })

  // ─── Start / cancel installation ──────────────────────────────────────────
  async function startInstall() {
    setInstallLogs([])
    setInstallError(null)
    setInstalling(true)

    const controller = new AbortController()
    installAbortRef.current = controller

    try {
      const response = await installStreamApi.run(installConfig, controller.signal)
      if (!response.ok) {
        const text = await response.text().catch(() => `HTTP ${response.status}`)
        setInstallError(text)
        setInstalling(false)
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
              setInstallLogs((prev) => {
                const next = [...prev, payload.line as string]
                return next.length > 5000 ? next.slice(-5000) : next
              })
              setTimeout(() => installBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 0)
            }
            if (payload.done) {
              setInstalling(false)
              checkQuery.refetch()
            }
          } catch { /* ignore */ }
        }
      }
    } catch (err: unknown) {
      if ((err as { name?: string }).name !== 'AbortError') {
        setInstallError(String(err))
      }
    } finally {
      setInstalling(false)
    }
  }

  function cancelInstall() {
    installAbortRef.current?.abort()
    setInstalling(false)
    setInstallLogs((prev) => [...prev, '--- Installation cancelled by user ---'])
  }


  const worldConfQuery = useQuery<{ content: string }>({
    queryKey: ['worldserver-conf'],
    queryFn: () => installApi.worldserverConf().then((r) => r.data),
    enabled: configTab === 'worldserver',
  })

  const authConfQuery = useQuery<{ content: string }>({
    queryKey: ['authserver-conf'],
    queryFn: () => installApi.authserverConf().then((r) => r.data),
    enabled: configTab === 'authserver',
  })

  const activeConf = configTab === 'worldserver' ? worldConfQuery.data?.content : authConfQuery.data?.content
  const displayedConf = editedConf ?? activeConf ?? ''

  const saveMut = useMutation({
    mutationFn: () =>
      configTab === 'worldserver'
        ? installApi.saveWorldserverConf(displayedConf)
        : installApi.saveAuthserverConf(displayedConf),
    onSuccess: () => {
      setSaveMsg('Saved successfully!')
      setEditedConf(null)
      setTimeout(() => setSaveMsg(null), 3000)
    },
    onError: () => setSaveMsg('Save failed — check server logs'),
  })

  const checks = checkQuery.data
  const allGood = checks && Object.values(checks).every(Boolean)
  const isLoading = configTab === 'worldserver' ? worldConfQuery.isLoading : authConfQuery.isLoading

  return (
    <div className="space-y-4">
      {/* System Checks */}
      <Card>
        <CardHeader
          title="System Checks"
          subtitle="Verifies that AzerothCore is correctly installed"
          action={
            <Button variant="ghost" size="sm" icon={<RefreshCw size={13} />}
              loading={checkQuery.isRefetching} onClick={() => checkQuery.refetch()}>
              Refresh
            </Button>
          }
        />

        {checkQuery.isLoading && <p className="text-panel-muted text-sm">Checking…</p>}

        {checks && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
              {(Object.keys(CHECK_LABELS) as (keyof InstallCheck)[]).map((key) => (
                <div key={key} className="flex items-center gap-3">
                  {checks[key]
                    ? <CheckCircle2 size={16} className="text-success shrink-0" />
                    : <XCircle size={16} className="text-danger shrink-0" />
                  }
                  <span className={`text-sm ${checks[key] ? 'text-gray-300' : 'text-danger'}`}>
                    {CHECK_LABELS[key]}
                  </span>
                </div>
              ))}
            </div>

            {allGood ? (
              <div className="bg-success/10 border border-success/30 text-success text-sm rounded-lg px-4 py-3">
                ✓ All checks passed — AzerothCore is ready.
              </div>
            ) : (
              <div className="bg-warning/10 border border-warning/30 text-warning text-sm rounded-lg px-4 py-3">
                ⚠ Some checks failed. Use the installer below to set up AzerothCore.
              </div>
            )}
          </>
        )}
      </Card>

      {/* Run Installation */}
      <Card>
        <CardHeader
          title="Run Installation"
          subtitle="Clone, compile, and set up AzerothCore automatically (may take 30–90 minutes)"
        />
        {/* Repository selection */}
        <div className="mb-5">
          <p className="text-xs font-medium text-panel-muted uppercase tracking-wide mb-2">Repository</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {REPO_OPTIONS.map((opt) => {
              const selected = installConfig.repository_url === opt.value
              return (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selected
                      ? 'border-brand bg-brand/10'
                      : 'border-panel-border hover:border-brand/50'
                  } ${installing ? 'opacity-50 pointer-events-none' : ''}`}
                >
                  <input
                    type="radio"
                    name="repository_url"
                    value={opt.value}
                    checked={selected}
                    disabled={installing}
                    onChange={() => setInstallConfig((prev) => ({
                      ...prev,
                      repository_url: opt.value,
                      // Auto-select the correct default branch for each repo
                      clone_branch: opt.value === 'https://github.com/mod-playerbots/azerothcore-wotlk.git'
                        ? 'Playerbot'
                        : 'master',
                    }))}
                    className="mt-0.5 accent-brand"
                  />
                  <div>
                    <p className="text-sm font-medium text-white">{opt.label}</p>
                    <p className="text-xs text-panel-muted mt-0.5">{opt.description}</p>
                  </div>
                </label>
              )
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          {[
            { key: 'ac_path',          label: 'Install Path',        type: 'text',     placeholder: '/opt/azerothcore' },
            { key: 'clone_branch',     label: 'Git Branch',          type: 'text',     placeholder: 'master' },
            { key: 'db_host',          label: 'MySQL Host',          type: 'text',     placeholder: '127.0.0.1' },
            { key: 'db_root_password', label: 'MySQL Root Password', type: 'password', placeholder: 'leave empty to use UNIX socket auth (Debian/Ubuntu default)' },
            { key: 'db_user',          label: 'AC MySQL User',       type: 'text',     placeholder: 'acore' },
            { key: 'db_password',      label: 'AC MySQL Password',   type: 'password', placeholder: '••••••••' },
          ].map(({ key, label, type, placeholder }) => (
            <div key={key} className="space-y-1.5">
              <label className="text-xs font-medium text-panel-muted uppercase tracking-wide">{label}</label>
              <input
                type={type}
                value={installConfig[key as keyof typeof installConfig]}
                disabled={installing}
                onChange={(e) => setInstallConfig((prev) => ({ ...prev, [key]: e.target.value }))}
                placeholder={placeholder}
                className="w-full bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-brand disabled:opacity-50"
              />
            </div>
          ))}
        </div>

        <div className="flex gap-3 mb-4">
          {!installing ? (
            <Button icon={<Play size={15} />} onClick={startInstall}>Start Installation</Button>
          ) : (
            <Button variant="danger" icon={<StopCircle size={15} />} onClick={cancelInstall}>Cancel</Button>
          )}
          <Button variant="ghost" size="sm" icon={<RotateCcw size={14} />}
            onClick={() => setInstallLogs([])} disabled={installing}>
            Clear Output
          </Button>
        </div>

        {installError && (
          <div className="bg-danger/10 border border-danger/30 text-danger text-sm rounded-lg px-4 py-3 mb-3">
            ✕ {installError}
          </div>
        )}

        {(installLogs.length > 0 || installing) && (
          <div className="bg-panel-bg border border-panel-border rounded-lg max-h-72 overflow-y-auto p-3">
            {installLogs.map((line, i) => (
              <div key={i} className={`font-mono text-xs leading-5 ${
                line.includes('[error]') || line.startsWith('---') ? 'text-danger'
                : line.startsWith('[step:') ? 'text-brand-light font-semibold'
                : line.includes('[done]') ? 'text-success'
                : 'text-gray-300'
              }`}>{line}</div>
            ))}
            {installing && (
              <div className="font-mono text-xs text-panel-muted animate-pulse">▌ Running…</div>
            )}
            <div ref={installBottomRef} />
          </div>
        )}
      </Card>

      {/* Config editor */}
      <Card padding={false}>
        <div className="flex items-center justify-between p-4 border-b border-panel-border">
          <div className="flex gap-1">
            {(['worldserver', 'authserver'] as ConfigTab[]).map((t) => (
              <button key={t} onClick={() => { setConfigTab(t); setEditedConf(null); setSaveMsg(null) }}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors ${
                  configTab === t ? 'bg-brand text-white' : 'text-panel-muted hover:text-white'
                }`}>
                {t}.conf
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            {saveMsg && <span className={`text-xs ${saveMsg.includes('fail') ? 'text-danger' : 'text-success'}`}>{saveMsg}</span>}
            <Button size="sm" icon={<Save size={13} />}
              loading={saveMut.isPending}
              disabled={!editedConf}
              onClick={() => saveMut.mutate()}>
              Save
            </Button>
          </div>
        </div>

        {isLoading && <p className="text-panel-muted text-sm p-4">Loading config…</p>}

        {!isLoading && (
          <textarea
            value={displayedConf}
            onChange={(e) => setEditedConf(e.target.value)}
            spellCheck={false}
            rows={30}
            className="w-full bg-panel-bg font-mono text-xs text-gray-300 px-4 py-3 outline-none resize-none rounded-b-xl leading-5"
            placeholder="Config file content will appear here…"
          />
        )}
      </Card>
    </div>
  )
}

