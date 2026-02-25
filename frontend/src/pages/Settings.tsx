import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, XCircle, Loader2, Save, RefreshCw } from 'lucide-react'
import { settingsApi } from '@/services/api'
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
