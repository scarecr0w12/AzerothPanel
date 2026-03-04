import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, Square, RotateCcw, Terminal, Plus, Pencil, Trash2, X, Server, FileText, ChevronRight, ChevronDown, ChevronUp } from 'lucide-react'
import {
  useServerStatus,
  useStartAuth, useStopAuth, useRestartAuth,
  useInstances, useStartInstance, useStopInstance, useRestartInstance,
  useCreateInstance, useUpdateInstance, useDeleteInstance,
} from '@/hooks/useServerStatus'
import { instancesApi, settingsApi } from '@/services/api'
import { Card, CardHeader } from '@/components/ui/Card'
import StatusBadge from '@/components/ui/StatusBadge'
import Button from '@/components/ui/Button'
import { toast } from '@/components/ui/Toast'
import type {
  WorldServerInstance,
  WorldServerInstanceCreate,
  WorldServerInstanceUpdate,
  WorldServerProvisionRequest,
  ProcessStatus,
} from '@/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmtUptime(s?: number) {
  if (!s) return '—'
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

// ---------------------------------------------------------------------------
// Generic server card used for the authserver
// ---------------------------------------------------------------------------
function ServerCard({
  label, running, loading,
  onStart, onStop, onRestart,
  startLoading, stopLoading, restartLoading,
  status,
}: {
  label: string
  running?: boolean
  loading: boolean
  onStart: () => void; onStop: () => void; onRestart: () => void
  startLoading: boolean; stopLoading: boolean; restartLoading: boolean
  status?: ProcessStatus
}) {
  return (
    <Card>
      <CardHeader
        title={label}
        action={<StatusBadge status={loading ? 'starting' : running ? 'online' : 'offline'} />}
      />
      <dl className="grid grid-cols-2 gap-3 text-sm mb-5">
        {([
          ['PID', status?.pid ?? '—'],
          ['Uptime', fmtUptime(status?.uptime_seconds)],
          ['CPU', running ? `${status?.cpu_percent ?? 0}%` : '—'],
          ['Memory', running ? `${Math.round(status?.memory_mb ?? 0)} MB` : '—'],
        ] as [string, string | number][]).map(([k, v]) => (
          <div key={k}>
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

// ---------------------------------------------------------------------------
// Individual worldserver instance card (with inline console + config editor)
// ---------------------------------------------------------------------------
type InstanceTab = 'status' | 'config'

function InstanceCard({
  inst,
  onEdit,
  onDelete,
}: {
  inst: WorldServerInstance
  onEdit: (inst: WorldServerInstance) => void
  onDelete: (inst: WorldServerInstance) => void
}) {
  const startMut = useStartInstance(inst.id)
  const stopMut = useStopInstance(inst.id)
  const restartMut = useRestartInstance(inst.id)
  const [cmd, setCmd] = useState('')
  const [cmdResult, setCmdResult] = useState<string | null>(null)
  const [cmdLoading, setCmdLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<InstanceTab>('status')

  // Config tab state
  const [configDraft, setConfigDraft] = useState<string | null>(null)
  const [configSaving, setConfigSaving] = useState(false)
  const [configSaveMsg, setConfigSaveMsg] = useState<string | null>(null)

  const { data: configData, isLoading: configLoading, refetch: refetchConfig } = useQuery({
    queryKey: ['instance-config', inst.id],
    queryFn: () => instancesApi.getConfig(inst.id).then(r => r.data as { content: string }),
    enabled: activeTab === 'config',
    staleTime: 60_000,
  })

  function handleTabChange(tab: InstanceTab) {
    setActiveTab(tab)
    setConfigDraft(null)
    setConfigSaveMsg(null)
    if (tab === 'config') refetchConfig()
  }

  async function saveConfig() {
    const content = configDraft ?? configData?.content ?? ''
    setConfigSaving(true)
    setConfigSaveMsg(null)
    try {
      await instancesApi.saveConfig(inst.id, content)
      setConfigSaveMsg('Saved successfully.')
      setConfigDraft(null)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setConfigSaveMsg('Error: ' + (err.response?.data?.detail ?? 'Unknown error'))
    } finally {
      setConfigSaving(false)
    }
  }

  const running = inst.status?.running

  async function sendCommand() {
    if (!cmd.trim()) return
    setCmdLoading(true)
    try {
      const { data } = await instancesApi.command(inst.id, cmd)
      setCmdResult(data.result)
      setCmd('')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setCmdResult('Error: ' + (err.response?.data?.detail ?? 'Unknown error'))
    } finally {
      setCmdLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title={inst.display_name}
        action={
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => onEdit(inst)}
              className="p-1 rounded text-panel-muted hover:text-white hover:bg-panel-hover transition-colors"
              title="Edit instance"
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={() => onDelete(inst)}
              className="p-1 rounded text-panel-muted hover:text-danger hover:bg-danger/10 transition-colors"
              title="Delete instance"
            >
              <Trash2 size={13} />
            </button>
            <StatusBadge status={running ? 'online' : 'offline'} />
          </div>
        }
      />

      {inst.process_name !== 'worldserver' && (
        <p className="text-xs text-panel-muted mb-3 font-mono">{inst.process_name}</p>
      )}

      {/* Tab bar */}
      <div className="flex gap-0.5 mb-4 bg-panel-bg rounded-lg p-0.5">
        {(['status', 'config'] as InstanceTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => handleTabChange(tab)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-medium transition-colors capitalize ${
              activeTab === tab
                ? 'bg-panel-surface text-white shadow-sm'
                : 'text-panel-muted hover:text-white'
            }`}
          >
            {tab === 'status' ? <Server size={11} /> : <FileText size={11} />}
            {tab}
          </button>
        ))}
      </div>

      {/* ── Status tab ── */}
      {activeTab === 'status' && (
        <>
          <dl className="grid grid-cols-2 gap-3 text-sm mb-4">
            {([
              ['PID', inst.status?.pid ?? '—'],
              ['Uptime', fmtUptime(inst.status?.uptime_seconds)],
              ['CPU', running ? `${inst.status?.cpu_percent ?? 0}%` : '—'],
              ['Memory', running ? `${Math.round(inst.status?.memory_mb ?? 0)} MB` : '—'],
            ] as [string, string | number][]).map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-panel-muted">{k}</dt>
                <dd className="text-white font-mono font-medium mt-0.5">{v}</dd>
              </div>
            ))}
          </dl>

          <div className="flex flex-wrap gap-2 mb-4">
            <Button variant="success" size="sm" icon={<Play size={13} />}
              loading={startMut.isPending} disabled={running} onClick={() => startMut.mutate()}>Start</Button>
            <Button variant="danger" size="sm" icon={<Square size={13} />}
              loading={stopMut.isPending} disabled={!running} onClick={() => stopMut.mutate()}>Stop</Button>
            <Button variant="secondary" size="sm" icon={<RotateCcw size={13} />}
              loading={restartMut.isPending} onClick={() => restartMut.mutate()}>Restart</Button>
          </div>

          {/* Inline console */}
          <div className="border-t border-panel-border pt-4">
            <p className="text-xs text-panel-muted mb-2 flex items-center gap-1">
              <Terminal size={11} /> GM Console
            </p>
            {!running && (
              <p className="mb-2 text-xs text-warning bg-warning/10 border border-warning/20 rounded px-2 py-1">
                Server offline — start it first
              </p>
            )}
            <div className="flex gap-2">
              <input
                value={cmd} onChange={(e) => setCmd(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendCommand()}
                placeholder=".server info"
                disabled={!running}
                className="flex-1 bg-panel-bg border border-panel-border rounded-lg px-3 py-1.5 text-xs text-white placeholder-panel-muted outline-none font-mono disabled:opacity-40"
              />
              <Button size="sm" onClick={sendCommand} loading={cmdLoading} disabled={!cmd.trim() || !running}>
                Run
              </Button>
            </div>
            {cmdResult && (
              <pre className="mt-2 bg-panel-bg border border-panel-border rounded-lg p-2 text-xs font-mono text-green-400 whitespace-pre-wrap max-h-36 overflow-y-auto">
                {cmdResult}
              </pre>
            )}
          </div>
        </>
      )}

      {/* ── Config tab ── */}
      {activeTab === 'config' && (
        <div className="space-y-3">
          {inst.conf_path ? (
            <p className="text-xs text-panel-muted font-mono truncate">
              <span className="text-brand">conf:</span> {inst.conf_path}
            </p>
          ) : (
            <p className="text-xs text-warning bg-warning/10 border border-warning/20 rounded px-2 py-1">
              No dedicated conf file — using global worldserver.conf.
              Edit the instance to generate one.
            </p>
          )}

          {configLoading ? (
            <p className="text-xs text-panel-muted animate-pulse py-4 text-center">Loading config…</p>
          ) : (
            <>
              <textarea
                className="w-full h-64 bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-xs text-white font-mono outline-none focus:border-brand resize-y"
                value={configDraft ?? configData?.content ?? ''}
                onChange={(e) => setConfigDraft(e.target.value)}
                spellCheck={false}
              />
              <div className="flex items-center gap-2">
                <Button size="sm" loading={configSaving} onClick={saveConfig}
                  disabled={configDraft === null && !configData?.content}>
                  Save Config
                </Button>
                {configDraft !== null && (
                  <Button size="sm" variant="secondary" onClick={() => setConfigDraft(null)}>
                    Discard
                  </Button>
                )}
                {configSaveMsg && (
                  <span className={`text-xs ${configSaveMsg.startsWith('Error') ? 'text-danger' : 'text-green-400'}`}>
                    {configSaveMsg}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Create / Edit modal  (multi-step for Create)
// ---------------------------------------------------------------------------
interface ModalBasicData {
  display_name: string
  process_name: string
  binary_path: string
  working_dir: string
  notes: string
}

interface AdvancedData {
  ac_path: string
  build_path: string
  char_db_host: string
  char_db_port: string
  char_db_user: string
  char_db_password: string
  char_db_name: string
  soap_host: string
  soap_port: string
  soap_user: string
  soap_password: string
}

function InstanceModal({
  initial,
  onClose,
  onSave,
  onSaveWithProvision,
  saving,
}: {
  initial?: WorldServerInstance
  onClose: () => void
  /** Called for edit (no provision step) */
  onSave: (data: WorldServerInstanceUpdate) => void
  /** Called for create: basic data + optional provision request */
  onSaveWithProvision: (basic: WorldServerInstanceCreate, provision: WorldServerProvisionRequest | null) => void
  saving: boolean
}) {
  const isEdit = !!initial

  // Load panel settings to derive config path defaults
  const { data: settingsData } = useQuery({
    queryKey: ['panel-settings'],
    queryFn: () => settingsApi.get().then(r => r.data as Record<string, string>),
    staleTime: 300_000,
  })

  // Step 1 — basic fields
  const [step, setStep] = useState(1)
  const [basic, setBasic] = useState<ModalBasicData>({
    display_name: initial?.display_name ?? '',
    process_name: initial?.process_name ?? '',
    binary_path: initial?.binary_path ?? '',
    working_dir: initial?.working_dir ?? '',
    notes: initial?.notes ?? '',
  })

  // Advanced per-instance overrides
  const [advanced, setAdvanced] = useState<AdvancedData>({
    ac_path:          initial?.ac_path          ?? '',
    build_path:       initial?.build_path        ?? '',
    char_db_host:     initial?.char_db_host      ?? '',
    char_db_port:     initial?.char_db_port      ?? '',
    char_db_user:     initial?.char_db_user      ?? '',
    char_db_password: initial?.char_db_password  ?? '',
    char_db_name:     initial?.char_db_name      ?? '',
    soap_host:        initial?.soap_host         ?? '',
    soap_port:        initial?.soap_port         ?? '',
    soap_user:        initial?.soap_user         ?? '',
    soap_password:    initial?.soap_password     ?? '',
  })
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Step 2 — provision / config generation
  const [generateConf, setGenerateConf] = useState(true)
  const [provision, setProvision] = useState<WorldServerProvisionRequest>({
    conf_output_path: '',
    realm_name: 'AzerothCore 2',
    worldserver_port: 8086,
    instance_port: 8087,
    ra_port: 3445,
    realm_id: 2,
    realm_address: '',
  })

  // Auto-fill conf_output_path from AC_CONF_PATH setting when process name changes
  function handleProcessNameChange(v: string) {
    setBasic(b => ({ ...b, process_name: v }))
    // Derive conf dir from the panel setting (AC_CONF_PATH) so it matches the
    // actual installation layout instead of using a hardcoded path.
    const confDir = settingsData?.AC_CONF_PATH?.replace(/\/$/, '') ??
      (settingsData?.AC_WORLDSERVER_CONF
        ? settingsData.AC_WORLDSERVER_CONF.replace(/\/[^/]+$/, '')
        : '/opt/azerothcore/etc')
    setProvision(p => {
      const isDefault = p.conf_output_path === '' ||
        /worldserver-[a-zA-Z0-9_-]*\.conf$/.test(p.conf_output_path)
      return isDefault
        ? { ...p, conf_output_path: `${confDir}/worldserver-${v}.conf` }
        : p
    })
  }

  function handleStep1Submit(e: React.FormEvent) {
    e.preventDefault()
    if (isEdit) {
      onSave({ display_name: basic.display_name, binary_path: basic.binary_path, working_dir: basic.working_dir, notes: basic.notes, ...advanced })
    } else {
      setStep(2)
    }
  }

  function handleStep2Submit(e: React.FormEvent) {
    e.preventDefault()
    onSaveWithProvision(
      { display_name: basic.display_name, process_name: basic.process_name, binary_path: basic.binary_path, working_dir: basic.working_dir, notes: basic.notes, ...advanced },
      generateConf ? { ...provision } : null,
    )
  }

  const labelCls = 'block text-xs text-panel-muted mb-1'
  const inputCls =
    'w-full bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-sm text-white placeholder-panel-muted outline-none focus:border-brand font-mono'
  const numInputCls = inputCls + ' [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="bg-panel-surface border border-panel-border rounded-xl w-full max-w-md shadow-2xl flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-panel-border shrink-0">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Server size={15} />
            {isEdit ? `Edit: ${initial?.display_name}` : 'Add Worldserver Instance'}
          </h2>
          <div className="flex items-center gap-3">
            {!isEdit && (
              <div className="flex items-center gap-1 text-xs text-panel-muted">
                <span className={step === 1 ? 'text-white font-medium' : ''}>1. Info</span>
                <ChevronRight size={11} />
                <span className={step === 2 ? 'text-white font-medium' : ''}>2. Configure</span>
              </div>
            )}
            <button onClick={onClose} className="text-panel-muted hover:text-white transition-colors">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Step 1 */}
        {step === 1 && (
          <form onSubmit={handleStep1Submit} className="overflow-y-auto p-5 space-y-4">
            <div>
              <label className={labelCls}>Display Name *</label>
              <input required value={basic.display_name} onChange={e => setBasic(b => ({ ...b, display_name: e.target.value }))}
                placeholder="PTR Server" className={inputCls} />
            </div>

            {!isEdit && (
              <div>
                <label className={labelCls}>Process Name * (unique daemon identifier)</label>
                <input required value={basic.process_name} onChange={e => handleProcessNameChange(e.target.value)}
                  placeholder="worldserver-ptr" className={inputCls}
                  pattern="[a-zA-Z0-9_-]+" title="Letters, numbers, hyphens and underscores only" />
                <p className="mt-1 text-xs text-panel-muted">
                  Must be unique — the daemon tracks this process by name (e.g.{' '}
                  <code className="text-brand">worldserver-ptr</code>).
                </p>
              </div>
            )}

            <div>
              <label className={labelCls}>Binary Path (blank → use AC_BINARY_PATH from Settings)</label>
              <input value={basic.binary_path} onChange={e => setBasic(b => ({ ...b, binary_path: e.target.value }))}
                placeholder="/opt/azerothcore/bin/worldserver" className={inputCls} />
            </div>

            <div>
              <label className={labelCls}>Working Directory (blank → use AC_BINARY_PATH from Settings)</label>
              <input value={basic.working_dir} onChange={e => setBasic(b => ({ ...b, working_dir: e.target.value }))}
                placeholder="/opt/azerothcore/bin" className={inputCls} />
            </div>

            <div>
              <label className={labelCls}>Notes (optional)</label>
              <input value={basic.notes} onChange={e => setBasic(b => ({ ...b, notes: e.target.value }))}
                placeholder="Seasonal realm, long-term test, …" className={inputCls} />
            </div>

            {/* Per-instance overrides */}
            <div className="border border-panel-border rounded-lg overflow-hidden">
              <button
                type="button"
                onClick={() => setShowAdvanced(v => !v)}
                className="w-full flex items-center justify-between px-3 py-2.5 text-xs text-panel-muted hover:text-white hover:bg-panel-hover transition-colors"
              >
                <span className="font-medium">Per-Instance Overrides{' '}
                  <span className="font-normal">(optional — blank = use global settings)</span>
                </span>
                {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              </button>
              {showAdvanced && (
                <div className="p-4 space-y-3 border-t border-panel-border bg-panel-bg/40">
                  <p className="text-xs text-panel-muted">Values here override the global Settings for this instance only.</p>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelCls}>Source Path (ac_path)</label>
                      <input value={advanced.ac_path} onChange={e => setAdvanced(a => ({ ...a, ac_path: e.target.value }))}
                        placeholder="(global AC_PATH)" className={inputCls} />
                    </div>
                    <div>
                      <label className={labelCls}>Build Path (build_path)</label>
                      <input value={advanced.build_path} onChange={e => setAdvanced(a => ({ ...a, build_path: e.target.value }))}
                        placeholder="(global AC_BUILD_PATH)" className={inputCls} />
                    </div>
                  </div>

                  <p className="text-xs text-panel-muted border-t border-panel-border pt-3">Characters DB (overrides global AC_CHAR_DB_*)</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelCls}>Host</label>
                      <input value={advanced.char_db_host} onChange={e => setAdvanced(a => ({ ...a, char_db_host: e.target.value }))}
                        placeholder="(global)" className={inputCls} />
                    </div>
                    <div>
                      <label className={labelCls}>Port</label>
                      <input value={advanced.char_db_port} onChange={e => setAdvanced(a => ({ ...a, char_db_port: e.target.value }))}
                        placeholder="3306" className={inputCls} />
                    </div>
                    <div>
                      <label className={labelCls}>User</label>
                      <input value={advanced.char_db_user} onChange={e => setAdvanced(a => ({ ...a, char_db_user: e.target.value }))}
                        placeholder="(global)" className={inputCls} />
                    </div>
                    <div>
                      <label className={labelCls}>Password</label>
                      <input type="password" value={advanced.char_db_password} onChange={e => setAdvanced(a => ({ ...a, char_db_password: e.target.value }))}
                        placeholder="(global)" className={inputCls} />
                    </div>
                    <div className="col-span-2">
                      <label className={labelCls}>Database Name</label>
                      <input value={advanced.char_db_name} onChange={e => setAdvanced(a => ({ ...a, char_db_name: e.target.value }))}
                        placeholder="(global)" className={inputCls} />
                    </div>
                  </div>

                  <p className="text-xs text-panel-muted border-t border-panel-border pt-3">SOAP (overrides global AC_SOAP_*)</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelCls}>Host</label>
                      <input value={advanced.soap_host} onChange={e => setAdvanced(a => ({ ...a, soap_host: e.target.value }))}
                        placeholder="(global)" className={inputCls} />
                    </div>
                    <div>
                      <label className={labelCls}>Port</label>
                      <input value={advanced.soap_port} onChange={e => setAdvanced(a => ({ ...a, soap_port: e.target.value }))}
                        placeholder="7878" className={inputCls} />
                    </div>
                    <div>
                      <label className={labelCls}>GM Account</label>
                      <input value={advanced.soap_user} onChange={e => setAdvanced(a => ({ ...a, soap_user: e.target.value }))}
                        placeholder="(global)" className={inputCls} />
                    </div>
                    <div>
                      <label className={labelCls}>GM Password</label>
                      <input type="password" value={advanced.soap_password} onChange={e => setAdvanced(a => ({ ...a, soap_password: e.target.value }))}
                        placeholder="(global)" className={inputCls} />
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex gap-2 pt-1">
              {isEdit ? (
                <Button type="submit" loading={saving} className="flex-1">Save Changes</Button>
              ) : (
                <Button type="submit" className="flex-1">
                  Next: Configure <ChevronRight size={13} />
                </Button>
              )}
              <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
            </div>
          </form>
        )}

        {/* Step 2 — provision config */}
        {step === 2 && (
          <form onSubmit={handleStep2Submit} className="overflow-y-auto p-5 space-y-4">
            {/* Generate conf toggle */}
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={generateConf}
                onChange={e => setGenerateConf(e.target.checked)}
                className="mt-0.5 accent-brand"
              />
              <div>
                <p className="text-sm text-white font-medium">Generate a worldserver.conf for this instance</p>
                <p className="text-xs text-panel-muted mt-0.5">
                  Copies the global worldserver.conf as a template and patches the ports, realm name and realm ID.
                  Recommended for all secondary instances.
                </p>
              </div>
            </label>

            {generateConf && (
              <div className="space-y-4 border-t border-panel-border pt-4">
                <div>
                  <label className={labelCls}>Config Output Path *</label>
                  <input required value={provision.conf_output_path}
                    onChange={e => setProvision(p => ({ ...p, conf_output_path: e.target.value }))}
                    placeholder="/opt/azerothcore/etc/worldserver-ptr.conf"
                    className={inputCls} />
                  <p className="mt-1 text-xs text-panel-muted">
                    Full path where the new <code className="text-brand">worldserver.conf</code> will be written on the host.
                  </p>
                </div>

                <div>
                  <label className={labelCls}>Realm Name</label>
                  <input value={provision.realm_name ?? ''}
                    onChange={e => setProvision(p => ({ ...p, realm_name: e.target.value }))}
                    placeholder="AzerothCore 2" className={inputCls} />
                </div>

                <div>
                  <label className={labelCls}>Realm Address (blank → copy from main realm)</label>
                  <input value={provision.realm_address ?? ''}
                    onChange={e => setProvision(p => ({ ...p, realm_address: e.target.value || undefined }))}
                    placeholder="10.10.20.132 — leave blank to inherit" className={inputCls} />
                  <p className="mt-1 text-xs text-panel-muted">
                    IP/hostname written to <code className="text-brand">realmlist</code>.
                    Leave blank to copy from the main realm entry.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelCls}>Realm ID</label>
                    <input type="number" value={provision.realm_id ?? 2}
                      onChange={e => setProvision(p => ({ ...p, realm_id: parseInt(e.target.value) || 2 }))}
                      min={1} className={numInputCls} />
                  </div>
                  <div>
                    <label className={labelCls}>WorldServer Port</label>
                    <input type="number" value={provision.worldserver_port ?? 8086}
                      onChange={e => setProvision(p => ({ ...p, worldserver_port: parseInt(e.target.value) || 8086 }))}
                      min={1024} max={65535} className={numInputCls} />
                  </div>
                  <div>
                    <label className={labelCls}>Instance Port</label>
                    <input type="number" value={provision.instance_port ?? 8087}
                      onChange={e => setProvision(p => ({ ...p, instance_port: parseInt(e.target.value) || 8087 }))}
                      min={1024} max={65535} className={numInputCls} />
                  </div>
                  <div>
                    <label className={labelCls}>RA Port</label>
                    <input type="number" value={provision.ra_port ?? 3445}
                      onChange={e => setProvision(p => ({ ...p, ra_port: parseInt(e.target.value) || 3445 }))}
                      min={1024} max={65535} className={numInputCls} />
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <Button type="button" variant="secondary" onClick={() => setStep(1)}>
                ← Back
              </Button>
              <Button type="submit" loading={saving} className="flex-1">
                {generateConf ? 'Create & Generate Config' : 'Create Instance'}
              </Button>
              <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------
export default function ServerControl() {
  const { data: status, isLoading: statusLoading } = useServerStatus(3000)
  const startAuth = useStartAuth()
  const stopAuth = useStopAuth()
  const restartAuth = useRestartAuth()

  const { data: instancesData } = useInstances()
  const createMut = useCreateInstance()
  const deleteMut = useDeleteInstance()
  const queryClient = useQueryClient()

  const [showCreate, setShowCreate] = useState(false)
  const [editTarget, setEditTarget] = useState<WorldServerInstance | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<WorldServerInstance | null>(null)
  const [provisionError, setProvisionError] = useState<string | null>(null)

  const updateMut = useUpdateInstance(editTarget?.id ?? 0)

  const a = status?.authserver
  const instances = instancesData?.instances ?? []

  /** Create → optionally generate config → close modal */
  async function handleCreateWithProvision(
    basic: WorldServerInstanceCreate,
    provision: WorldServerProvisionRequest | null,
  ) {
    setProvisionError(null)
    createMut.mutate(basic, {
      onSuccess: async (created) => {
        if (provision) {
          try {
            const result = await instancesApi.generateConfig(created.id, provision)
            const msg = (result.data as { message?: string }).message ?? 'Config generated successfully.'
            toast(msg, 'success')
            // Invalidate instances so the new conf_path shows up immediately
            await queryClient.invalidateQueries({ queryKey: ['worldserver-instances'] })
          } catch (e: unknown) {
            const err = e as { response?: { data?: { detail?: string } } }
            setProvisionError(
              'Instance created, but config generation failed: ' +
              (err.response?.data?.detail ?? 'Unknown error')
            )
          }
        }
        setShowCreate(false)
      },
    })
  }

  function handleEditSave(data: WorldServerInstanceUpdate) {
    updateMut.mutate(data, {
      onSuccess: () => setEditTarget(null),
    })
  }

  function handleDelete(inst: WorldServerInstance) {
    deleteMut.mutate(inst.id, {
      onSuccess: () => setDeleteConfirm(null),
    })
  }

  return (
    <div className="space-y-6">

      {/* ── Authserver ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ServerCard
          label="Authserver"
          running={a?.running} loading={statusLoading}
          status={a}
          onStart={() => startAuth.mutate()} startLoading={startAuth.isPending}
          onStop={() => stopAuth.mutate()} stopLoading={stopAuth.isPending}
          onRestart={() => restartAuth.mutate()} restartLoading={restartAuth.isPending}
        />
      </div>

      {/* ── Worldserver Instances ──────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Server size={15} className="text-brand" />
            Worldserver Instances
            <span className="text-xs text-panel-muted font-normal">({instances.length})</span>
          </h2>
          <Button size="sm" icon={<Plus size={13} />} onClick={() => { setProvisionError(null); setShowCreate(true) }}>
            Add Instance
          </Button>
        </div>

        {provisionError && (
          <div className="mb-3 px-3 py-2 rounded-lg bg-danger/10 border border-danger/30 text-xs text-danger">
            {provisionError}
          </div>
        )}

        {instances.length === 0 ? (
          <Card>
            <p className="text-sm text-panel-muted text-center py-4">
              No worldserver instances found. Click{' '}
              <strong className="text-white">Add Instance</strong> to create one.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {instances.map((inst) => (
              <InstanceCard
                key={inst.id}
                inst={inst}
                onEdit={(i) => setEditTarget(i)}
                onDelete={(i) => setDeleteConfirm(i)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Create modal ───────────────────────────────────────────────── */}
      {showCreate && (
        <InstanceModal
          onClose={() => setShowCreate(false)}
          onSave={() => {/* not used for create */}}
          onSaveWithProvision={handleCreateWithProvision}
          saving={createMut.isPending}
        />
      )}

      {/* ── Edit modal ─────────────────────────────────────────────────── */}
      {editTarget && (
        <InstanceModal
          initial={editTarget}
          onClose={() => setEditTarget(null)}
          onSave={handleEditSave}
          onSaveWithProvision={() => {/* not used for edit */}}
          saving={updateMut.isPending}
        />
      )}

      {/* ── Delete confirm ─────────────────────────────────────────────── */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-panel-surface border border-panel-border rounded-xl w-full max-w-sm shadow-2xl p-5">
            <h2 className="text-sm font-semibold text-white mb-2">Delete Instance</h2>
            <p className="text-sm text-panel-muted mb-5">
              Are you sure you want to delete{' '}
              <strong className="text-white">{deleteConfirm.display_name}</strong>?{' '}
              The running process will be stopped first.
            </p>
            <div className="flex gap-2">
              <Button
                variant="danger"
                loading={deleteMut.isPending}
                onClick={() => handleDelete(deleteConfirm)}
                className="flex-1"
              >
                Delete
              </Button>
              <Button variant="secondary" onClick={() => setDeleteConfirm(null)}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
