import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, XCircle, Loader2, Save, RefreshCw, Github, DownloadCloud, GitBranch, Tag } from 'lucide-react'
import { settingsApi, modulesApi } from '@/services/api'
import type { PanelSettings } from '@/types'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function Field({
  label, name, value, onChange, type = 'text',
}: {
  label: string
  name: string
  value: string
  onChange: (name: string, val: string) => void
  type?: string
}) {
  return (
    <div>
      <label className="block text-xs text-panel-muted mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(name, e.target.value)}
        className="w-full bg-panel-bg border border-panel-border rounded-lg px-3 py-2
                   text-sm text-white placeholder-panel-muted
                   focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand"
      />
    </div>
  )
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-panel-surface border border-panel-border rounded-xl p-5">
      <h3 className="text-sm font-semibold text-white mb-4 pb-2 border-b border-panel-border">{title}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{children}</div>
    </div>
  )
}

// ─── Test-connection button ───────────────────────────────────────────────────

function TestDbButton({
  host, port, user, password, db_name,
}: { host: string; port: string; user: string; password: string; db_name: string }) {
  const [state, setState] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [msg, setMsg] = useState('')

  const test = async () => {
    setState('loading')
    try {
      const res = await settingsApi.testDb({ host, port, user, password, db_name })
      if (res.data.success) { setState('ok'); setMsg('Connected') }
      else { setState('error'); setMsg(res.data.error ?? 'Failed') }
    } catch (e: unknown) {
      setState('error')
      setMsg(e instanceof Error ? e.message : 'Request failed')
    }
    setTimeout(() => setState('idle'), 4000)
  }

  return (
    <div className="sm:col-span-2 flex items-center gap-3">
      <button
        onClick={test}
        disabled={state === 'loading'}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
                   bg-panel-hover text-gray-300 hover:text-white border border-panel-border
                   disabled:opacity-50 transition-colors"
      >
        {state === 'loading' ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
        Test Connection
      </button>
      {state === 'ok'    && <span className="flex items-center gap-1 text-xs text-success"><CheckCircle size={13}/>{msg}</span>}
      {state === 'error' && <span className="flex items-center gap-1 text-xs text-danger"><XCircle size={13}/>{msg}</span>}
    </div>
  )
}



// ─── Panel Update section ────────────────────────────────────────────────────

interface PanelVersionInfo {
  success: boolean
  commit?: string
  branch?: string
  version?: string
  commits_behind?: number | null
  message?: string
}

function PanelUpdateSection() {
  const [info, setInfo] = useState<PanelVersionInfo | null>(null)
  const [checking, setChecking] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [updateOutput, setUpdateOutput] = useState('')
  const [updateError, setUpdateError] = useState('')
  const [updateSuccess, setUpdateSuccess] = useState(false)

  const checkVersion = async () => {
    setChecking(true)
    setInfo(null)
    try {
      const res = await settingsApi.panelVersion()
      setInfo(res.data as PanelVersionInfo)
    } catch (e: unknown) {
      setInfo({ success: false, message: e instanceof Error ? e.message : 'Failed to reach daemon' })
    } finally {
      setChecking(false)
    }
  }

  const runUpdate = async () => {
    setUpdating(true)
    setUpdateOutput('')
    setUpdateError('')
    setUpdateSuccess(false)
    try {
      const res = await settingsApi.updatePanel()
      const d = res.data as { success: boolean; message: string; output?: string }
      setUpdateOutput(d.output ?? d.message)
      setUpdateSuccess(true)
      // Re-check version after update
      await checkVersion()
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'response' in e) {
        const axiosErr = e as { response?: { data?: { detail?: string } } }
        setUpdateError(axiosErr.response?.data?.detail ?? 'Update failed')
      } else {
        setUpdateError(e instanceof Error ? e.message : 'Update failed')
      }
    } finally {
      setUpdating(false)
    }
  }

  return (
    <div className="bg-panel-surface border border-panel-border rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4 pb-2 border-b border-panel-border">
        <DownloadCloud size={15} className="text-white" />
        <h3 className="text-sm font-semibold text-white">Panel Update</h3>
      </div>

      <p className="text-xs text-panel-muted mb-4">
        Pull the latest AzerothPanel code from GitHub and rebuild the containers.
        The host daemon must be running (<code className="text-xs font-mono text-brand-light">make daemon-start</code>).
        The panel will automatically restart after a successful update.
      </p>

      {/* Version info */}
      {info && info.success && (
        <div className="flex flex-wrap gap-4 mb-4 text-xs text-panel-muted">
          <span className="flex items-center gap-1"><Tag size={12} className="text-brand-light" />{info.version}</span>
          <span className="flex items-center gap-1"><GitBranch size={12} className="text-brand-light" />{info.branch}</span>
          <span className="flex items-center gap-1 font-mono">{info.commit}</span>
          {info.commits_behind != null && (
            <span className={`flex items-center gap-1 font-medium ${
              info.commits_behind > 0 ? 'text-yellow-400' : 'text-success'
            }`}>
              {info.commits_behind > 0
                ? `${info.commits_behind} commit(s) behind origin`
                : 'Up to date'}
            </span>
          )}
        </div>
      )}
      {info && !info.success && (
        <div className="flex items-center gap-1 mb-4 text-xs text-danger">
          <XCircle size={12} />{info.message}
        </div>
      )}

      {/* Buttons */}
      <div className="flex flex-wrap gap-2 items-center">
        <button
          onClick={checkVersion}
          disabled={checking || updating}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
                     bg-panel-hover text-gray-300 hover:text-white border border-panel-border
                     disabled:opacity-50 transition-colors"
        >
          {checking ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          Check for Updates
        </button>

        <button
          onClick={runUpdate}
          disabled={updating || checking}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
                     bg-brand text-white hover:bg-brand/90
                     disabled:opacity-50 transition-colors"
        >
          {updating ? <Loader2 size={13} className="animate-spin" /> : <DownloadCloud size={13} />}
          {updating ? 'Updating…' : 'Update Panel'}
        </button>
      </div>

      {/* Output */}
      {(updateOutput || updateError) && (
        <div className={`mt-4 rounded-lg border p-3 ${
          updateError
            ? 'border-danger/30 bg-danger/5'
            : 'border-success/30 bg-success/5'
        }`}>
          {updateSuccess && (
            <div className="flex items-center gap-1 text-xs text-success mb-2 font-medium">
              <CheckCircle size={13} /> Update completed – containers are restarting
            </div>
          )}
          {updateError && (
            <div className="flex items-center gap-1 text-xs text-danger mb-2 font-medium">
              <XCircle size={13} /> {updateError}
            </div>
          )}
          {updateOutput && (
            <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto max-h-64 overflow-y-auto">{
              updateOutput
            }</pre>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Test GitHub token button ─────────────────────────────────────────────────

function TestGithubButton() {
  const [state, setState] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [msg, setMsg] = useState('')

  const test = async () => {
    setState('loading')
    try {
      const res = await modulesApi.rateLimit()
      const d = res.data as { limit: number; remaining: number; authenticated: boolean }
      if (d.authenticated) {
        setState('ok')
        setMsg(`Token valid — ${d.remaining}/${d.limit} requests remaining`)
      } else {
        setState('ok')
        setMsg(`No token — ${d.remaining}/${d.limit} requests remaining (unauthenticated)`)
      }
    } catch {
      setState('error')
      setMsg('Failed to reach GitHub API')
    }
    setTimeout(() => setState('idle'), 6000)
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <button
        onClick={test}
        disabled={state === 'loading'}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
                   bg-panel-hover text-gray-300 hover:text-white border border-panel-border
                   disabled:opacity-50 transition-colors"
      >
        {state === 'loading' ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
        Test Token / Rate Limit
      </button>
      {state === 'ok'    && <span className="flex items-center gap-1 text-xs text-success"><CheckCircle size={13}/>{msg}</span>}
      {state === 'error' && <span className="flex items-center gap-1 text-xs text-danger"><XCircle size={13}/>{msg}</span>}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

const EMPTY: PanelSettings = {
  AC_PATH: '', AC_BUILD_PATH: '', AC_BINARY_PATH: '',
  AC_CONF_PATH: '', AC_LOG_PATH: '', AC_DATA_PATH: '',
  AC_WORLDSERVER_CONF: '', AC_AUTHSERVER_CONF: '', AC_CLIENT_PATH: '',
  AC_AUTH_DB_HOST: '', AC_AUTH_DB_PORT: '3306', AC_AUTH_DB_USER: '',
  AC_AUTH_DB_PASSWORD: '', AC_AUTH_DB_NAME: '',
  AC_CHAR_DB_HOST: '', AC_CHAR_DB_PORT: '3306', AC_CHAR_DB_USER: '',
  AC_CHAR_DB_PASSWORD: '', AC_CHAR_DB_NAME: '',
  AC_WORLD_DB_HOST: '', AC_WORLD_DB_PORT: '3306', AC_WORLD_DB_USER: '',
  AC_WORLD_DB_PASSWORD: '', AC_WORLD_DB_NAME: '',
  AC_SOAP_HOST: '', AC_SOAP_PORT: '7878', AC_SOAP_USER: '', AC_SOAP_PASSWORD: '',
  AC_RA_HOST: '', AC_RA_PORT: '3443',
  GITHUB_TOKEN: '',
}

export default function Settings() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<PanelSettings>(EMPTY)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')

  const { isLoading, data: settingsData } = useQuery({
    queryKey: ['panel-settings'],
    queryFn: async () => {
      const res = await settingsApi.get()
      return res.data as PanelSettings
    },
  })

  useEffect(() => {
    if (settingsData) setForm(settingsData)
  }, [settingsData])

  const mutation = useMutation({
    mutationFn: (updates: Partial<PanelSettings>) =>
      settingsApi.update(updates as Record<string, string>),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['panel-settings'] })
      setSaved(true)
      setSaveError('')
      setTimeout(() => setSaved(false), 3000)
    },
    onError: (e: unknown) => {
      setSaveError(e instanceof Error ? e.message : 'Save failed')
    },
  })

  const set = (name: string, val: string) =>
    setForm(prev => ({ ...prev, [name]: val }))

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-panel-muted">
        <Loader2 size={24} className="animate-spin mr-2" /> Loading settings…
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-sm text-panel-muted mt-1">
            AzerothCore paths, database connections and SOAP credentials.
            Changes take effect immediately without a restart.
          </p>
        </div>
        <button
          onClick={() => mutation.mutate(form)}
          disabled={mutation.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                     bg-brand text-white hover:bg-brand/90 disabled:opacity-50 transition-colors"
        >
          {mutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
          Save Settings
        </button>
      </div>

      {/* Feedback banners */}
      {saved && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-success/10 border border-success/30 text-success text-sm">
          <CheckCircle size={16} /> Settings saved successfully.
        </div>
      )}
      {saveError && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
          <XCircle size={16} /> {saveError}
        </div>
      )}

      {/* ── Paths ── */}
      <SectionCard title="AzerothCore Paths">
        <Field label="Source Path (AC_PATH)"         name="AC_PATH"              value={form.AC_PATH}              onChange={set} />
        <Field label="Build Path (AC_BUILD_PATH)"    name="AC_BUILD_PATH"        value={form.AC_BUILD_PATH}        onChange={set} />
        <Field label="Binary Path (AC_BINARY_PATH)"  name="AC_BINARY_PATH"       value={form.AC_BINARY_PATH}       onChange={set} />
        <Field label="Config Path (AC_CONF_PATH)"    name="AC_CONF_PATH"         value={form.AC_CONF_PATH}         onChange={set} />
        <Field label="Log Path (AC_LOG_PATH)"        name="AC_LOG_PATH"          value={form.AC_LOG_PATH}          onChange={set} />
        <Field label="Data Path (AC_DATA_PATH)"      name="AC_DATA_PATH"         value={form.AC_DATA_PATH}         onChange={set} />
        <Field label="Client Path (AC_CLIENT_PATH)"  name="AC_CLIENT_PATH"       value={form.AC_CLIENT_PATH}       onChange={set} />
        <Field label="Worldserver Conf"              name="AC_WORLDSERVER_CONF"  value={form.AC_WORLDSERVER_CONF}  onChange={set} />
        <Field label="Authserver Conf"               name="AC_AUTHSERVER_CONF"   value={form.AC_AUTHSERVER_CONF}   onChange={set} />
      </SectionCard>

      {/* ── Auth DB ── */}
      <SectionCard title="Auth Database (acore_auth)">
        <Field label="Host"     name="AC_AUTH_DB_HOST"     value={form.AC_AUTH_DB_HOST}     onChange={set} />
        <Field label="Port"     name="AC_AUTH_DB_PORT"     value={form.AC_AUTH_DB_PORT}     onChange={set} />
        <Field label="User"     name="AC_AUTH_DB_USER"     value={form.AC_AUTH_DB_USER}     onChange={set} />
        <Field label="Password" name="AC_AUTH_DB_PASSWORD" value={form.AC_AUTH_DB_PASSWORD} onChange={set} type="password" />
        <Field label="Database" name="AC_AUTH_DB_NAME"     value={form.AC_AUTH_DB_NAME}     onChange={set} />
        <TestDbButton
          host={form.AC_AUTH_DB_HOST} port={form.AC_AUTH_DB_PORT}
          user={form.AC_AUTH_DB_USER} password={form.AC_AUTH_DB_PASSWORD}
          db_name={form.AC_AUTH_DB_NAME}
        />
      </SectionCard>

      {/* ── Characters DB ── */}
      <SectionCard title="Characters Database (acore_characters)">
        <Field label="Host"     name="AC_CHAR_DB_HOST"     value={form.AC_CHAR_DB_HOST}     onChange={set} />
        <Field label="Port"     name="AC_CHAR_DB_PORT"     value={form.AC_CHAR_DB_PORT}     onChange={set} />
        <Field label="User"     name="AC_CHAR_DB_USER"     value={form.AC_CHAR_DB_USER}     onChange={set} />
        <Field label="Password" name="AC_CHAR_DB_PASSWORD" value={form.AC_CHAR_DB_PASSWORD} onChange={set} type="password" />
        <Field label="Database" name="AC_CHAR_DB_NAME"     value={form.AC_CHAR_DB_NAME}     onChange={set} />
        <TestDbButton
          host={form.AC_CHAR_DB_HOST} port={form.AC_CHAR_DB_PORT}
          user={form.AC_CHAR_DB_USER} password={form.AC_CHAR_DB_PASSWORD}
          db_name={form.AC_CHAR_DB_NAME}
        />
      </SectionCard>

      {/* ── World DB ── */}
      <SectionCard title="World Database (acore_world)">
        <Field label="Host"     name="AC_WORLD_DB_HOST"     value={form.AC_WORLD_DB_HOST}     onChange={set} />
        <Field label="Port"     name="AC_WORLD_DB_PORT"     value={form.AC_WORLD_DB_PORT}     onChange={set} />
        <Field label="User"     name="AC_WORLD_DB_USER"     value={form.AC_WORLD_DB_USER}     onChange={set} />
        <Field label="Password" name="AC_WORLD_DB_PASSWORD" value={form.AC_WORLD_DB_PASSWORD} onChange={set} type="password" />
        <Field label="Database" name="AC_WORLD_DB_NAME"     value={form.AC_WORLD_DB_NAME}     onChange={set} />
        <TestDbButton
          host={form.AC_WORLD_DB_HOST} port={form.AC_WORLD_DB_PORT}
          user={form.AC_WORLD_DB_USER} password={form.AC_WORLD_DB_PASSWORD}
          db_name={form.AC_WORLD_DB_NAME}
        />
      </SectionCard>

      {/* ── SOAP ── */}
      <SectionCard title="SOAP (GM Commands via Worldserver)">
        <Field label="SOAP Host"     name="AC_SOAP_HOST"     value={form.AC_SOAP_HOST}     onChange={set} />
        <Field label="SOAP Port"     name="AC_SOAP_PORT"     value={form.AC_SOAP_PORT}     onChange={set} />
        <Field label="GM Account"    name="AC_SOAP_USER"     value={form.AC_SOAP_USER}     onChange={set} />
        <Field label="GM Password"   name="AC_SOAP_PASSWORD" value={form.AC_SOAP_PASSWORD} onChange={set} type="password" />
      </SectionCard>

      {/* ── Panel Update ── */}
      <PanelUpdateSection />

      {/* ── GitHub ── */}
      <div className="bg-panel-surface border border-panel-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4 pb-2 border-b border-panel-border">
          <Github size={15} className="text-white" />
          <h3 className="text-sm font-semibold text-white">GitHub Integration</h3>
        </div>
        <p className="text-xs text-panel-muted mb-4">
          Unauthenticated GitHub API requests are rate-limited to <strong className="text-white">10 searches/minute</strong>.
          Providing a Personal Access Token raises this to <strong className="text-white">30 searches/minute</strong> and
          is required for browsing the module catalogue reliably.
          Create a token at{' '}
          <a
            href="https://github.com/settings/tokens"
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand-light hover:underline"
          >
            github.com/settings/tokens
          </a>{' '}
          (no scopes required for public repo search).
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="block text-xs text-panel-muted mb-1">Personal Access Token</label>
            <input
              type="password"
              value={form.GITHUB_TOKEN}
              onChange={e => set('GITHUB_TOKEN', e.target.value)}
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
              className="w-full bg-panel-bg border border-panel-border rounded-lg px-3 py-2
                         text-sm text-white placeholder-panel-muted
                         focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand font-mono"
            />
          </div>
          <div className="sm:col-span-2">
            <TestGithubButton />
          </div>
        </div>
      </div>

      {/* ── Save footer ── */}
      <div className="flex justify-end pb-4">
        <button
          onClick={() => mutation.mutate(form)}
          disabled={mutation.isPending}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium
                     bg-brand text-white hover:bg-brand/90 disabled:opacity-50 transition-colors"
        >
          {mutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
          Save Settings
        </button>
      </div>
    </div>
  )
}
