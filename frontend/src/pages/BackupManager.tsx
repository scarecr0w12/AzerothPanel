import { useEffect, useRef, useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Archive, Plus, Trash2, CheckCircle2, XCircle, Terminal, X,
  HardDrive, Globe, Cloud, RefreshCw, Play, RotateCcw,
  FolderOpen, Wifi, WifiOff, ChevronDown, ChevronUp,
  AlertTriangle, Clock, FileText, Database, Server,
} from 'lucide-react'
import { backupApi } from '@/services/api'
import { Card } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import type {
  BackupDestination, BackupDestinationCreate, BackupDestType,
  BackupJob, BackupFile,
} from '@/types'

// ──────────────────────────────────────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────────────────────────────────────
const DEST_TYPES: { value: BackupDestType; label: string; icon: typeof HardDrive }[] = [
  { value: 'local',    label: 'Local Filesystem', icon: HardDrive },
  { value: 'sftp',     label: 'SFTP',             icon: Globe },
  { value: 'ftp',      label: 'FTP / FTPS',       icon: Globe },
  { value: 's3',       label: 'AWS S3',            icon: Cloud },
  { value: 'gdrive',   label: 'Google Drive',      icon: Cloud },
  { value: 'onedrive', label: 'OneDrive',          icon: Cloud },
]

const DEST_LABELS: Record<BackupDestType, string> = {
  local:    'Local',
  sftp:     'SFTP',
  ftp:      'FTP',
  s3:       'AWS S3',
  gdrive:   'Google Drive',
  onedrive: 'OneDrive',
}

function defaultConfig(type: BackupDestType): Record<string, unknown> {
  switch (type) {
    case 'local':    return { path: '/opt/azerothpanel-backups' }
    case 'sftp':     return { host: '', port: '22', username: '', password: '', private_key: '', path: '/backups' }
    case 'ftp':      return { host: '', port: '21', username: '', password: '', path: '/backups', tls: false }
    case 's3':       return { access_key_id: '', secret_access_key: '', bucket: '', region: 'us-east-1', prefix: 'azeroth-backups/' }
    case 'gdrive':   return { service_account_json: '', folder_id: '' }
    case 'onedrive': return { client_id: '', client_secret: '', tenant_id: '', folder_path: '/backups', drive_id: '' }
  }
}

function fmtBytes(n: number): string {
  if (n >= 1_073_741_824) return `${(n / 1_073_741_824).toFixed(1)} GB`
  if (n >= 1_048_576)     return `${(n / 1_048_576).toFixed(1)} MB`
  if (n >= 1_024)         return `${(n / 1_024).toFixed(1)} KB`
  return `${n} B`
}

function fmtDate(s: string): string {
  if (!s) return '—'
  try { return new Date(s).toLocaleString() } catch { return s }
}

// ──────────────────────────────────────────────────────────────────────────────
// Log panel (reusable)
// ──────────────────────────────────────────────────────────────────────────────
function LogPanel({
  logs, done, error, title, onClose,
}: {
  logs: string[]; done: boolean; error: string; title: string; onClose: () => void
}) {
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [logs])

  const isError  = !!error || logs.some(l => l.startsWith('[ERROR]'))
  const isDone   = done && !isError
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-3xl bg-panel-surface border border-panel-border rounded-xl flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-5 py-3 border-b border-panel-border">
          <div className="flex items-center gap-2">
            <Terminal size={16} className="text-brand" />
            <span className="font-medium text-white text-sm">{title}</span>
          </div>
          <div className="flex items-center gap-3">
            {done && isDone  && <span className="flex items-center gap-1 text-green-400 text-xs font-medium"><CheckCircle2 size={13}/> Done</span>}
            {done && isError && <span className="flex items-center gap-1 text-red-400   text-xs font-medium"><XCircle size={13}/> Error</span>}
            {!done           && <span className="text-yellow-400 text-xs animate-pulse">Running…</span>}
            {done && (
              <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
                <X size={18}/>
              </button>
            )}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 font-mono text-xs text-gray-300 space-y-0.5 bg-panel-bg rounded-b-xl">
          {logs.map((l, i) => {
            const col = l.startsWith('[ERROR]') ? 'text-red-400'
                      : l.startsWith('[WARN]')  ? 'text-yellow-400'
                      : l.startsWith('[DONE]')  ? 'text-green-400'
                      : l.startsWith('[INFO]')  ? 'text-blue-300'
                      : 'text-gray-300'
            return <p key={i} className={col}>{l}</p>
          })}
          <div ref={bottomRef}/>
        </div>
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
// Destination config form fields per type
// ──────────────────────────────────────────────────────────────────────────────
function ConfigFields({ type, cfg, onChange }: {
  type: BackupDestType
  cfg: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}) {
  const inp = (key: string, label: string, placeholder = '', type_ = 'text', className = '') => (
    <div key={key} className={`flex flex-col gap-1 ${className}`}>
      <label className="text-xs text-panel-muted font-medium uppercase tracking-wide">{label}</label>
      <input
        type={type_}
        value={String(cfg[key] ?? '')}
        onChange={e => onChange(key, e.target.value)}
        placeholder={placeholder}
        className="bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-brand"
      />
    </div>
  )
  const chk = (key: string, label: string) => (
    <label key={key} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
      <input
        type="checkbox"
        checked={Boolean(cfg[key])}
        onChange={e => onChange(key, e.target.checked)}
        className="w-4 h-4 accent-brand"
      />
      {label}
    </label>
  )
  const ta = (key: string, label: string, rows = 5) => (
    <div key={key} className="flex flex-col gap-1 col-span-2">
      <label className="text-xs text-panel-muted font-medium uppercase tracking-wide">{label}</label>
      <textarea
        value={String(cfg[key] ?? '')}
        onChange={e => onChange(key, e.target.value)}
        rows={rows}
        className="bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:ring-1 focus:ring-brand resize-y"
      />
    </div>
  )

  if (type === 'local') return (
    <div className="grid grid-cols-2 gap-3">
      {inp('path', 'Backup Directory', '/opt/azerothpanel-backups', 'text', 'col-span-2')}
    </div>
  )

  if (type === 'sftp') return (
    <div className="grid grid-cols-2 gap-3">
      {inp('host', 'Host', 'server.example.com')}
      {inp('port', 'Port', '22')}
      {inp('username', 'Username', 'backup-user')}
      {inp('password', 'Password', '', 'password')}
      {inp('path', 'Remote Path', '/backups', 'text', 'col-span-2')}
      {ta('private_key', 'Private Key (PEM) – leave blank to use password', 4)}
    </div>
  )

  if (type === 'ftp') return (
    <div className="grid grid-cols-2 gap-3">
      {inp('host', 'Host', 'ftp.example.com')}
      {inp('port', 'Port', '21')}
      {inp('username', 'Username')}
      {inp('password', 'Password', '', 'password')}
      {inp('path', 'Remote Path', '/backups', 'text', 'col-span-2')}
      <div className="col-span-2">{chk('tls', 'Use FTPS (TLS)')}</div>
    </div>
  )

  if (type === 's3') return (
    <div className="grid grid-cols-2 gap-3">
      {inp('access_key_id', 'Access Key ID')}
      {inp('secret_access_key', 'Secret Access Key', '', 'password')}
      {inp('bucket', 'Bucket Name', 'my-azeroth-backups')}
      {inp('region', 'Region', 'us-east-1')}
      {inp('prefix', 'Key Prefix (folder)', 'azeroth-backups/', 'text', 'col-span-2')}
    </div>
  )

  if (type === 'gdrive') return (
    <div className="grid grid-cols-2 gap-3">
      {inp('folder_id', 'Drive Folder ID', '1abc…123', 'text', 'col-span-2')}
      {ta('service_account_json', 'Service Account JSON (paste full JSON key file)', 8)}
      <p className="text-xs text-panel-muted col-span-2">
        Create a Service Account in Google Cloud Console, share the Drive folder with its email, then paste the JSON key here.
      </p>
    </div>
  )

  if (type === 'onedrive') return (
    <div className="grid grid-cols-2 gap-3">
      {inp('client_id', 'App (Client) ID')}
      {inp('tenant_id', 'Tenant ID')}
      {inp('client_secret', 'Client Secret', '', 'password')}
      {inp('folder_path', 'Folder Path', '/backups')}
      {inp('drive_id', 'Drive ID (optional – leave blank for personal OneDrive)', 'text', 'col-span-2')}
      <p className="text-xs text-panel-muted col-span-2">
        Register an app in Azure AD, grant Files.ReadWrite.All permission, and provide the client credentials above.
      </p>
    </div>
  )

  return null
}

// ──────────────────────────────────────────────────────────────────────────────
// Destination modal (create / edit)
// ──────────────────────────────────────────────────────────────────────────────
function DestinationModal({
  initial,
  onSave,
  onClose,
}: {
  initial?: BackupDestination
  onSave: (data: BackupDestinationCreate) => void
  onClose: () => void
}) {
  const [name,    setName]    = useState(initial?.name    ?? '')
  const [type,    setType]    = useState<BackupDestType>(initial?.type ?? 'local')
  const [enabled, setEnabled] = useState(initial?.enabled ?? true)
  const [cfg,     setCfg]     = useState<Record<string, unknown>>(
    initial?.config ? { ...initial.config } : defaultConfig('local')
  )

  // When type changes, reset config to defaults for that type
  const handleTypeChange = (t: BackupDestType) => {
    setType(t)
    setCfg(defaultConfig(t))
  }

  const handleCfgChange = (key: string, value: unknown) => {
    setCfg(prev => ({ ...prev, [key]: value }))
  }

  const handleSave = () => {
    if (!name.trim()) return
    onSave({ name, type, config: cfg, enabled })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl bg-panel-surface border border-panel-border rounded-xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-panel-border">
          <span className="font-semibold text-white">{initial ? 'Edit' : 'Add'} Backup Destination</span>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors"><X size={18}/></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Name */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-panel-muted font-medium uppercase tracking-wide">Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="My Backup Location"
              className="bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-brand"
            />
          </div>
          {/* Type */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-panel-muted font-medium uppercase tracking-wide">Type</label>
            <div className="grid grid-cols-3 gap-2">
              {DEST_TYPES.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => handleTypeChange(value)}
                  className={`px-3 py-2 rounded-lg border text-xs font-medium transition-colors ${
                    type === value
                      ? 'border-brand bg-brand/20 text-brand-light'
                      : 'border-panel-border text-gray-400 hover:border-brand/50 hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {/* Config fields */}
          <div className="border border-panel-border rounded-lg p-4 bg-panel-bg/30">
            <ConfigFields type={type} cfg={cfg} onChange={handleCfgChange}/>
          </div>
          {/* Enabled */}
          <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
            <input
              type="checkbox"
              checked={enabled}
              onChange={e => setEnabled(e.target.checked)}
              className="w-4 h-4 accent-brand"
            />
            Enabled
          </label>
        </div>
        <div className="px-5 py-4 border-t border-panel-border flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={!name.trim()}>
            {initial ? 'Save Changes' : 'Add Destination'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
// Tab: Destinations
// ──────────────────────────────────────────────────────────────────────────────
function DestinationsTab({ destinations, onRefetch }: { destinations: BackupDestination[]; onRefetch: () => void }) {
  const qc = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [editing,   setEditing]   = useState<BackupDestination | undefined>()
  const [testResult, setTestResult] = useState<Record<number, { ok: boolean; msg: string }>>({})
  const [testingId,  setTestingId]  = useState<number | null>(null)

  const createMut = useMutation({
    mutationFn: (d: BackupDestinationCreate) => backupApi.createDestination(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['backup-destinations'] }); setShowModal(false) },
  })
  const updateMut = useMutation({
    mutationFn: ({ id, d }: { id: number; d: Partial<BackupDestinationCreate> }) => backupApi.updateDestination(id, d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['backup-destinations'] }); setEditing(undefined) },
  })
  const deleteMut = useMutation({
    mutationFn: (id: number) => backupApi.deleteDestination(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backup-destinations'] }),
  })

  const handleTest = async (id: number) => {
    setTestingId(id)
    try {
      const res = await backupApi.testDestination(id)
      setTestResult(prev => ({ ...prev, [id]: { ok: res.data.success, msg: res.data.message } }))
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setTestResult(prev => ({ ...prev, [id]: { ok: false, msg: err.response?.data?.detail ?? 'Error' } }))
    } finally {
      setTestingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-panel-muted">Configure where your backups will be stored.</p>
        <Button size="sm" onClick={() => setShowModal(true)}>
          <Plus size={14} className="mr-1"/> Add Destination
        </Button>
      </div>

      {destinations.length === 0 && (
        <div className="text-center py-12 text-panel-muted">
          <Archive size={40} className="mx-auto mb-3 opacity-40"/>
          <p className="text-sm">No destinations configured yet.</p>
          <p className="text-xs mt-1">Add a destination to start backing up.</p>
        </div>
      )}

      <div className="space-y-3">
        {destinations.map(dest => {
          const tr = testResult[dest.id]
          return (
            <Card key={dest.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${dest.enabled ? 'bg-green-400' : 'bg-gray-500'}`}/>
                  <div>
                    <p className="font-medium text-white text-sm">{dest.name}</p>
                    <p className="text-xs text-panel-muted">{DEST_LABELS[dest.type]}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {tr && (
                    <span className={`text-xs flex items-center gap-1 ${tr.ok ? 'text-green-400' : 'text-red-400'}`}>
                      {tr.ok ? <Wifi size={12}/> : <WifiOff size={12}/>} {tr.msg}
                    </span>
                  )}
                  <Button
                    size="sm" variant="ghost"
                    disabled={testingId === dest.id}
                    onClick={() => handleTest(dest.id)}
                  >
                    {testingId === dest.id ? <RefreshCw size={13} className="animate-spin"/> : <Wifi size={13}/>}
                    <span className="ml-1">Test</span>
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(dest)}>Edit</Button>
                  <Button
                    size="sm" variant="ghost"
                    className="text-red-400 hover:text-red-300"
                    onClick={() => { if (confirm(`Delete destination "${dest.name}"?`)) deleteMut.mutate(dest.id) }}
                  >
                    <Trash2 size={13}/>
                  </Button>
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      {showModal && (
        <DestinationModal
          onSave={d => createMut.mutate(d)}
          onClose={() => setShowModal(false)}
        />
      )}
      {editing && (
        <DestinationModal
          initial={editing}
          onSave={d => updateMut.mutate({ id: editing.id, d })}
          onClose={() => setEditing(undefined)}
        />
      )}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
// Tab: Create Backup
// ──────────────────────────────────────────────────────────────────────────────
function CreateBackupTab({ destinations }: { destinations: BackupDestination[] }) {
  const qc = useQueryClient()
  const [destId,          setDestId]          = useState<number | null>(null)
  const [inclConfigs,     setInclConfigs]      = useState(true)
  const [inclDatabases,   setInclDatabases]    = useState(true)
  const [inclServerFiles, setInclServerFiles] = useState(false)
  const [notes,           setNotes]           = useState('')
  const [running,         setRunning]         = useState(false)
  const [logs,            setLogs]            = useState<string[]>([])
  const [done,            setDone]            = useState(false)
  const [errMsg,          setErrMsg]          = useState('')
  const abortRef = useRef<AbortController | null>(null)

  const startBackup = useCallback(async () => {
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setRunning(true)
    setLogs([])
    setDone(false)
    setErrMsg('')

    try {
      const res = await backupApi.runBackup(
        { destination_id: destId, include_configs: inclConfigs, include_databases: inclDatabases, include_server_files: inclServerFiles, notes },
        ctrl.signal,
      )
      const reader = res.body?.getReader()
      if (!reader) throw new Error('No body')
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done: d, value } = await reader.read()
        if (d) break
        buf += dec.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''
        for (const chunk of parts) {
          const dataLine = chunk.trim()
          if (!dataLine.startsWith('data:')) continue
          const json = JSON.parse(dataLine.slice(5).trim())
          if (json.line)  setLogs(prev => [...prev, json.line])
          if (json.done)  { setDone(true); qc.invalidateQueries({ queryKey: ['backup-jobs'] }) }
          if (json.error) { setErrMsg(json.error); setDone(true) }
        }
      }
    } catch (e: unknown) {
      const err = e as { name?: string; message?: string }
      if (err?.name !== 'AbortError') setErrMsg(String(err?.message ?? e))
      setDone(true)
    } finally {
      setRunning(false)
    }
  }, [destId, inclConfigs, inclDatabases, inclServerFiles, notes, qc])

  return (
    <div className="space-y-5">
      <p className="text-sm text-panel-muted">Configure and run a new backup.</p>

      {/* Destination */}
      <Card className="p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <FolderOpen size={15} className="text-brand"/> Destination
        </h3>
        <div className="grid grid-cols-1 gap-2">
          <button
            onClick={() => setDestId(null)}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg border text-sm transition-colors ${
              destId === null
                ? 'border-brand bg-brand/10 text-white'
                : 'border-panel-border text-gray-400 hover:border-brand/40 hover:text-white'
            }`}
          >
            <HardDrive size={15}/>
            <div className="text-left">
              <p className="font-medium">Default Local Storage</p>
              <p className="text-xs opacity-70">/opt/azerothpanel-backups</p>
            </div>
          </button>
          {destinations.filter(d => d.enabled).map(d => (
            <button
              key={d.id}
              onClick={() => setDestId(d.id)}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg border text-sm transition-colors ${
                destId === d.id
                  ? 'border-brand bg-brand/10 text-white'
                  : 'border-panel-border text-gray-400 hover:border-brand/40 hover:text-white'
              }`}
            >
              <Cloud size={15}/>
              <div className="text-left">
                <p className="font-medium">{d.name}</p>
                <p className="text-xs opacity-70">{DEST_LABELS[d.type]}</p>
              </div>
            </button>
          ))}
          {destinations.filter(d => d.enabled).length === 0 && (
            <p className="text-xs text-panel-muted">No enabled destinations – only local storage available.</p>
          )}
        </div>
      </Card>

      {/* What to include */}
      <Card className="p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Archive size={15} className="text-brand"/> What to Include
        </h3>
        <div className="space-y-3">
          {[
            { key: 'configs',     state: inclConfigs,     set: setInclConfigs,     label: 'Config Files',    desc: 'All .conf files from AC_CONF_PATH', Icon: FileText },
            { key: 'databases',   state: inclDatabases,   set: setInclDatabases,   label: 'Databases',       desc: 'auth, characters, world (mysqldump)', Icon: Database },
            { key: 'serverfiles', state: inclServerFiles, set: setInclServerFiles, label: 'Server Binaries', desc: 'Executables from AC_BINARY_PATH', Icon: Server },
          ].map(({ key, state, set, label, desc, Icon }) => (
            <label key={key} className="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={state}
                onChange={e => set(e.target.checked)}
                className="w-4 h-4 accent-brand"
              />
              <Icon size={15} className="text-brand/60 group-hover:text-brand transition-colors shrink-0"/>
              <div>
                <p className="text-sm text-white font-medium">{label}</p>
                <p className="text-xs text-panel-muted">{desc}</p>
              </div>
            </label>
          ))}
        </div>
        {inclServerFiles && (
          <div className="flex items-start gap-2 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
            <AlertTriangle size={14} className="text-yellow-400 mt-0.5 shrink-0"/>
            <p className="text-xs text-yellow-300">Server binary archives can be very large. Ensure you have sufficient storage.</p>
          </div>
        )}
      </Card>

      {/* Notes */}
      <Card className="p-5 space-y-3">
        <h3 className="text-sm font-semibold text-white">Notes (optional)</h3>
        <input
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="e.g. Pre-patch 3.4.0 backup"
          className="w-full bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-brand"
        />
      </Card>

      <Button
        onClick={startBackup}
        disabled={running || (!inclConfigs && !inclDatabases && !inclServerFiles)}
        className="w-full justify-center"
      >
        {running ? (
          <><RefreshCw size={15} className="mr-2 animate-spin"/> Running Backup…</>
        ) : (
          <><Play size={15} className="mr-2"/> Start Backup</>
        )}
      </Button>

      {(running || done) && (
        <LogPanel
          logs={logs}
          done={done}
          error={errMsg}
          title="Backup Progress"
          onClose={() => { setDone(false); setLogs([]) }}
        />
      )}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
// Tab: Job History
// ──────────────────────────────────────────────────────────────────────────────
function JobHistoryTab({ jobs, onRefetch, destinations }: {
  jobs: BackupJob[]; onRefetch: () => void; destinations: BackupDestination[]
}) {
  const qc = useQueryClient()
  const [expandedJob, setExpandedJob]   = useState<number | null>(null)
  const [jobFiles,    setJobFiles]      = useState<Record<number, BackupFile[]>>({})
  const [restoring,  setRestoring]     = useState<number | null>(null)
  const [restoreLogs,  setRestoreLogs]  = useState<string[]>([])
  const [restoreDone,  setRestoreDone]  = useState(false)
  const [restoreError, setRestoreError] = useState('')
  const [restoreOpts,  setRestoreOpts]  = useState({ restore_configs: true, restore_databases: true, restore_server_files: false })
  const [loadingFiles, setLoadingFiles] = useState<number | null>(null)

  const destMap = Object.fromEntries(destinations.map(d => [d.id, d]))

  const deleteMut = useMutation({
    mutationFn: (id: number) => backupApi.deleteJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backup-jobs'] }),
  })

  const toggleExpand = async (jobId: number) => {
    if (expandedJob === jobId) { setExpandedJob(null); return }
    setExpandedJob(jobId)
    if (!jobFiles[jobId]) {
      setLoadingFiles(jobId)
      try {
        const res = await backupApi.listJobFiles(jobId)
        setJobFiles(prev => ({ ...prev, [jobId]: res.data }))
      } catch { /* ignore */ } finally {
        setLoadingFiles(null)
      }
    }
  }

  const startRestore = async (job: BackupJob) => {
    setRestoring(job.id)
    setRestoreLogs([])
    setRestoreDone(false)
    setRestoreError('')
  }

  const confirmRestore = async () => {
    if (restoring === null) return
    const job = jobs.find(j => j.id === restoring)
    if (!job) return
    setRestoreLogs([])
    setRestoreDone(false)
    setRestoreError('')

    try {
      const res = await backupApi.restore(job.id, restoreOpts)
      const reader = res.body?.getReader()
      if (!reader) throw new Error('No body')
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done: d, value } = await reader.read()
        if (d) break
        buf += dec.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''
        for (const chunk of parts) {
          const dataLine = chunk.trim()
          if (!dataLine.startsWith('data:')) continue
          const json = JSON.parse(dataLine.slice(5).trim())
          if (json.line)  setRestoreLogs(prev => [...prev, json.line])
          if (json.done)  setRestoreDone(true)
          if (json.error) { setRestoreError(json.error); setRestoreDone(true) }
        }
      }
    } catch (e: unknown) {
      const err = e as { message?: string }
      setRestoreError(String(err?.message ?? e))
      setRestoreDone(true)
    }
  }

  const statusColor: Record<string, string> = {
    completed: 'text-green-400',
    running:   'text-yellow-400',
    failed:    'text-red-400',
    pending:   'text-gray-400',
  }
  const StatusIcon = ({ s }: { s: string }) => {
    if (s === 'completed') return <CheckCircle2 size={13} className="text-green-400"/>
    if (s === 'running')   return <RefreshCw    size={13} className="text-yellow-400 animate-spin"/>
    if (s === 'failed')    return <XCircle      size={13} className="text-red-400"/>
    return <Clock size={13} className="text-gray-400"/>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-panel-muted">History of all backup jobs.</p>
        <Button size="sm" variant="ghost" onClick={onRefetch}>
          <RefreshCw size={13} className="mr-1"/> Refresh
        </Button>
      </div>

      {jobs.length === 0 && (
        <div className="text-center py-12 text-panel-muted">
          <Clock size={40} className="mx-auto mb-3 opacity-40"/>
          <p className="text-sm">No backup jobs yet.</p>
        </div>
      )}

      <div className="space-y-2">
        {jobs.map(job => {
          const dest = job.destination_id ? destMap[job.destination_id] : null
          const expanded = expandedJob === job.id
          return (
            <Card key={job.id} className="overflow-hidden">
              {/* Row */}
              <div className="flex items-center gap-3 p-4">
                <StatusIcon s={job.status}/>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-sm font-medium ${statusColor[job.status] ?? 'text-white'}`}>
                      {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                    </span>
                    <span className="text-xs text-panel-muted">#{job.id}</span>
                    {job.notes && <span className="text-xs text-panel-muted truncate max-w-[200px]">{job.notes}</span>}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-panel-muted flex-wrap">
                    <span>{fmtDate(job.started_at)}</span>
                    {job.size_bytes > 0 && <span>{fmtBytes(job.size_bytes)}</span>}
                    {dest && <span>{dest.name} ({DEST_LABELS[dest.type]})</span>}
                    {!dest && job.local_path && <span>Local</span>}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-panel-muted">
                    {job.include_configs      && <span className="flex items-center gap-1"><FileText size={10}/> Configs</span>}
                    {job.include_databases    && <span className="flex items-center gap-1"><Database size={10}/> Databases</span>}
                    {job.include_server_files && <span className="flex items-center gap-1"><Server   size={10}/> Binaries</span>}
                  </div>
                  {job.error && <p className="text-xs text-red-400 mt-1 truncate">{job.error}</p>}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {job.status === 'completed' && (
                    <Button size="sm" variant="ghost" onClick={() => startRestore(job)}>
                      <RotateCcw size={13} className="mr-1"/> Restore
                    </Button>
                  )}
                  <button
                    onClick={() => toggleExpand(job.id)}
                    className="text-gray-400 hover:text-white transition-colors p-1"
                  >
                    {expanded ? <ChevronUp size={15}/> : <ChevronDown size={15}/>}
                  </button>
                  <Button
                    size="sm" variant="ghost"
                    className="text-red-400 hover:text-red-300"
                    onClick={() => { if (confirm(`Delete job #${job.id} record?`)) deleteMut.mutate(job.id) }}
                  >
                    <Trash2 size={13}/>
                  </Button>
                </div>
              </div>

              {/* Expanded: file list */}
              {expanded && (
                <div className="border-t border-panel-border p-4 bg-panel-bg/30">
                  <p className="text-xs font-semibold text-panel-muted uppercase tracking-wide mb-3">Files at Destination</p>
                  {loadingFiles === job.id ? (
                    <p className="text-xs text-panel-muted animate-pulse">Loading…</p>
                  ) : (jobFiles[job.id] ?? []).length === 0 ? (
                    <p className="text-xs text-panel-muted">No files found.</p>
                  ) : (
                    <div className="space-y-1">
                      {(jobFiles[job.id] ?? []).map(f => (
                        <div key={f.filename} className="flex items-center justify-between text-xs">
                          <span className="text-gray-300 font-mono">{f.filename}</span>
                          <div className="flex items-center gap-3 text-panel-muted">
                            <span>{fmtBytes(f.size_bytes)}</span>
                            <span>{fmtDate(f.modified)}</span>
                            <button
                              className="text-red-400 hover:text-red-300 transition-colors"
                              onClick={async () => {
                                if (!confirm(`Delete ${f.filename}?`)) return
                                await backupApi.deleteJobFile(job.id, f.filename)
                                setJobFiles(prev => ({
                                  ...prev,
                                  [job.id]: (prev[job.id] ?? []).filter(x => x.filename !== f.filename),
                                }))
                              }}
                            >
                              <Trash2 size={12}/>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Card>
          )
        })}
      </div>

      {/* Restore confirm modal */}
      {restoring !== null && !restoreLogs.length && !restoreDone && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-panel-surface border border-panel-border rounded-xl p-6 space-y-5">
            <div className="flex items-center gap-3">
              <RotateCcw size={18} className="text-brand"/>
              <h2 className="font-semibold text-white">Restore from Backup #{restoring}</h2>
            </div>
            <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <AlertTriangle size={14} className="text-red-400 mt-0.5 shrink-0"/>
              <p className="text-xs text-red-300">This will overwrite existing files. Make sure your server is stopped before restoring databases.</p>
            </div>
            <div className="space-y-3">
              {[
                { key: 'restore_configs',      label: 'Restore Config Files',    desc: 'Overwrites .conf files' },
                { key: 'restore_databases',    label: 'Restore Databases',       desc: 'Reimports SQL dumps' },
                { key: 'restore_server_files', label: 'Restore Server Binaries', desc: 'Overwrites binary files' },
              ].map(({ key, label, desc }) => (
                <label key={key} className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={restoreOpts[key as keyof typeof restoreOpts]}
                    onChange={e => setRestoreOpts(prev => ({ ...prev, [key]: e.target.checked }))}
                    className="w-4 h-4 accent-brand"
                  />
                  <div>
                    <p className="text-sm text-white font-medium">{label}</p>
                    <p className="text-xs text-panel-muted">{desc}</p>
                  </div>
                </label>
              ))}
            </div>
            <div className="flex justify-end gap-3">
              <Button variant="ghost" onClick={() => setRestoring(null)}>Cancel</Button>
              <Button onClick={confirmRestore} className="bg-red-600 hover:bg-red-700 border-red-500">
                <RotateCcw size={14} className="mr-1"/> Restore Now
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Restore progress */}
      {restoring !== null && (restoreLogs.length > 0 || restoreDone) && (
        <LogPanel
          logs={restoreLogs}
          done={restoreDone}
          error={restoreError}
          title="Restore Progress"
          onClose={() => { setRestoring(null); setRestoreLogs([]); setRestoreDone(false) }}
        />
      )}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
// Main page
// ──────────────────────────────────────────────────────────────────────────────
type Tab = 'destinations' | 'create' | 'history'

export default function BackupManager() {
  const [tab, setTab] = useState<Tab>('destinations')

  const { data: dests = [], refetch: refetchDests } = useQuery<BackupDestination[]>({
    queryKey: ['backup-destinations'],
    queryFn: async () => {
      const res = await backupApi.listDestinations()
      return res.data
    },
  })

  const { data: jobs = [], refetch: refetchJobs } = useQuery<BackupJob[]>({
    queryKey: ['backup-jobs'],
    queryFn: async () => {
      const res = await backupApi.listJobs()
      return res.data
    },
  })

  const TABS: { id: Tab; label: string }[] = [
    { id: 'destinations', label: 'Destinations' },
    { id: 'create',       label: 'Create Backup' },
    { id: 'history',      label: `Job History ${jobs.length > 0 ? `(${jobs.length})` : ''}` },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Archive size={22} className="text-brand"/>
        <div>
          <h1 className="text-xl font-bold text-white">Backup & Restore</h1>
          <p className="text-xs text-panel-muted mt-0.5">
            Back up configs, databases, and server files to local or cloud storage.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-panel-border">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.id
                ? 'border-brand text-brand-light'
                : 'border-transparent text-panel-muted hover:text-white'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'destinations' && <DestinationsTab destinations={dests} onRefetch={refetchDests}/>}
      {tab === 'create'       && <CreateBackupTab destinations={dests}/>}
      {tab === 'history'      && <JobHistoryTab   jobs={jobs} onRefetch={refetchJobs} destinations={dests}/>}
    </div>
  )
}
