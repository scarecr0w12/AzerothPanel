import { useRef, useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Download, HardDrive, CheckCircle2, XCircle, AlertTriangle, StopCircle, FolderOpen } from 'lucide-react'
import { dataExtractionApi, settingsApi } from '@/services/api'
import { Card, CardHeader } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import StatusBadge from '@/components/ui/StatusBadge'

interface ExtractionStatus {
  in_progress: boolean
  current_step: string | null
  progress_percent: number
  started_at: string | null
  error: string | null
  data_path: string
  has_dbc: boolean
  has_maps: boolean
  has_vmaps: boolean
  has_mmaps: boolean
  data_present: boolean
}

type Method = 'download' | 'extract'

export default function DataExtraction() {
  const [method, setMethod] = useState<Method>('download')
  const [logs, setLogs] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Extract options
  const [clientPath, setClientPath] = useState('')
  const [extractDbc, setExtractDbc] = useState(true)
  const [extractMaps, setExtractMaps] = useState(true)
  const [extractVmaps, setExtractVmaps] = useState(true)
  const [generateMmaps, setGenerateMmaps] = useState(false) // Off by default due to time

  // Fetch settings for default client path
  useEffect(() => {
    settingsApi.get().then((res) => {
      const settings = res.data as Record<string, string>
      if (settings.AC_CLIENT_PATH && !clientPath) {
        setClientPath(settings.AC_CLIENT_PATH)
      }
    }).catch(() => {
      // Ignore errors - user can enter path manually
    })
  }, [])

  // Query status
  const statusQuery = useQuery<ExtractionStatus>({
    queryKey: ['data-extraction-status'],
    queryFn: () => dataExtractionApi.status().then((r) => r.data),
    refetchInterval: running ? 1000 : 5000,
  })

  const status = statusQuery.data

  // Cancel mutation
  const cancelMut = useMutation({
    mutationFn: () => dataExtractionApi.cancel(),
    onSuccess: () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
      setRunning(false)
      setLogs((prev) => [...prev, '[cancelled] Operation cancelled by user'])
    },
  })

  // Start download
  async function startDownload() {
    setLogs([])
    setError(null)
    setRunning(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await dataExtractionApi.download(undefined, undefined, controller.signal)
      if (!response.ok) {
        const text = await response.text().catch(() => `HTTP ${response.status}`)
        setError(text)
        setRunning(false)
        return
      }

      await processStream(response)
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        setLogs((prev) => [...prev, '[cancelled] Download cancelled'])
      } else {
        setError(e instanceof Error ? e.message : 'Unknown error')
      }
    } finally {
      setRunning(false)
      abortRef.current = null
      statusQuery.refetch()
    }
  }

  // Start extraction
  async function startExtraction() {
    setLogs([])
    setError(null)
    setRunning(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await dataExtractionApi.extract(
        {
          client_path: clientPath || undefined,  // Send undefined if empty to use default from settings
          extract_dbc: extractDbc,
          extract_maps: extractMaps,
          extract_vmaps: extractVmaps,
          generate_mmaps: generateMmaps,
        },
        controller.signal
      )
      if (!response.ok) {
        const text = await response.text().catch(() => `HTTP ${response.status}`)
        setError(text)
        setRunning(false)
        return
      }

      await processStream(response)
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        setLogs((prev) => [...prev, '[cancelled] Extraction cancelled'])
      } else {
        setError(e instanceof Error ? e.message : 'Unknown error')
      }
    } finally {
      setRunning(false)
      abortRef.current = null
      statusQuery.refetch()
    }
  }

  // Process SSE stream
  async function processStream(response: Response) {
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
        const text = line.slice(6).trim()
        if (text) {
          setLogs((prev) => {
            const next = [...prev, text]
            return next.length > 5000 ? next.slice(-5000) : next
          })
          setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 0)
        }
      }
    }
  }

  // Cancel operation
  function cancel() {
    cancelMut.mutate()
  }

  // Data status indicators
  const dataIndicators = [
    { label: 'DBC', present: status?.has_dbc, required: true },
    { label: 'Maps', present: status?.has_maps, required: true },
    { label: 'VMaps', present: status?.has_vmaps, required: true },
    { label: 'MMaps', present: status?.has_mmaps, required: false },
  ]

  return (
    <div className="space-y-6">
      {/* Status Card */}
      <Card>
        <CardHeader
          title="Client Data Status"
          subtitle={status?.data_path || 'Loading...'}
          action={
            status?.data_present ? (
              <StatusBadge status="online" />
            ) : (
              <StatusBadge status="offline" />
            )
          }
        />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {dataIndicators.map(({ label, present, required }) => (
            <div
              key={label}
              className={`p-3 rounded-lg border ${
                present
                  ? 'bg-green-500/10 border-green-500/30'
                  : required
                  ? 'bg-red-500/10 border-red-500/30'
                  : 'bg-yellow-500/10 border-yellow-500/30'
              }`}
            >
              <div className="flex items-center gap-2">
                {present ? (
                  <CheckCircle2 size={16} className="text-green-400" />
                ) : required ? (
                  <XCircle size={16} className="text-red-400" />
                ) : (
                  <AlertTriangle size={16} className="text-yellow-400" />
                )}
                <span className="text-sm font-medium text-white">{label}</span>
              </div>
              <p className="text-xs text-panel-muted mt-1">
                {present ? 'Present' : required ? 'Missing' : 'Optional'}
              </p>
            </div>
          ))}
        </div>
        {!status?.data_present && (
          <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <p className="text-sm text-yellow-200">
              <AlertTriangle size={14} className="inline mr-2" />
              Client data is required before starting the servers. Use the options below to obtain it.
            </p>
          </div>
        )}
      </Card>

      {/* Method Selection */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Download Method */}
        <div
          className={`cursor-pointer transition-all bg-panel-surface border rounded-xl p-5 ${
            method === 'download' ? 'ring-2 ring-accent border-transparent' : 'border-panel-border hover:border-accent/50'
          }`}
          onClick={() => !running && setMethod('download')}
        >
          <CardHeader
            title="Download Pre-Extracted Data"
            subtitle="Recommended - Fast and easy"
            action={<Download size={18} className="text-accent" />}
          />
          <ul className="text-sm text-panel-muted space-y-1">
            <li>• Downloads ready-to-use data from AzerothCore (~1.5GB)</li>
            <li>• Includes DBC, Maps, VMaps, and MMaps</li>
            <li>• Takes 2-10 minutes depending on connection</li>
            <li>• No client installation required</li>
          </ul>
        </div>

        {/* Extract Method */}
        <div
          className={`cursor-pointer transition-all bg-panel-surface border rounded-xl p-5 ${
            method === 'extract' ? 'ring-2 ring-accent border-transparent' : 'border-panel-border hover:border-accent/50'
          }`}
          onClick={() => !running && setMethod('extract')}
        >
          <CardHeader
            title="Extract from Local Client"
            subtitle="For users with WoW 3.3.5a client"
            action={<HardDrive size={18} className="text-accent" />}
          />
          <ul className="text-sm text-panel-muted space-y-1">
            <li>• Requires World of Warcraft 3.3.5a (12340) client</li>
            <li>• Choose which data types to extract</li>
            <li>• MMaps generation takes 30-60 minutes</li>
            <li>• Useful for custom data or offline setup</li>
          </ul>
        </div>
      </div>

      {/* Download Method Controls */}
      {method === 'download' && (
        <Card>
          <CardHeader title="Download Client Data" subtitle="Pre-extracted data from wowgaming/client-data releases" />
          <div className="space-y-4">
            <p className="text-sm text-panel-muted">
              This will download <code className="text-accent">data.zip</code> (~1.5GB) from GitHub and extract it
              to your data directory.
            </p>
            <div className="flex gap-2">
              <Button
                variant="primary"
                icon={<Download size={14} />}
                loading={running}
                disabled={running}
                onClick={startDownload}
              >
                {running ? 'Downloading...' : 'Download Data'}
              </Button>
              {running && (
                <Button variant="danger" icon={<StopCircle size={14} />} onClick={cancel}>
                  Cancel
                </Button>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Extract Method Controls */}
      {method === 'extract' && (
        <Card>
          <CardHeader title="Extract from Client" subtitle="Requires WoW 3.3.5a (12340) client" />
          <div className="space-y-4">
            {/* Client Path */}
            <div>
              <label className="block text-sm font-medium text-white mb-1">Client Path</label>
              <div className="flex items-center gap-2 bg-panel-bg border border-panel-border rounded-lg px-3">
                <FolderOpen size={14} className="text-panel-muted shrink-0" />
                <input
                  type="text"
                  value={clientPath}
                  onChange={(e) => setClientPath(e.target.value)}
                  placeholder="/root/clientdata (default from settings)"
                  className="flex-1 bg-transparent py-2 text-sm text-white placeholder-panel-muted outline-none"
                  disabled={running}
                />
              </div>
              <p className="text-xs text-panel-muted mt-1">
                Path to your World of Warcraft 3.3.5a client directory. Leave empty to use default from settings.
              </p>
            </div>

            {/* Extraction Options */}
            <div>
              <label className="block text-sm font-medium text-white mb-2">Data Types to Extract</label>
              <div className="grid grid-cols-2 gap-2">
                <label className="flex items-center gap-2 p-2 bg-panel-bg border border-panel-border rounded-lg cursor-pointer hover:border-accent">
                  <input
                    type="checkbox"
                    checked={extractDbc}
                    onChange={(e) => setExtractDbc(e.target.checked)}
                    disabled={running}
                    className="accent-accent"
                  />
                  <span className="text-sm text-white">DBC Files</span>
                  <span className="text-xs text-green-400 ml-auto">Required</span>
                </label>
                <label className="flex items-center gap-2 p-2 bg-panel-bg border border-panel-border rounded-lg cursor-pointer hover:border-accent">
                  <input
                    type="checkbox"
                    checked={extractMaps}
                    onChange={(e) => setExtractMaps(e.target.checked)}
                    disabled={running}
                    className="accent-accent"
                  />
                  <span className="text-sm text-white">Maps</span>
                  <span className="text-xs text-green-400 ml-auto">Required</span>
                </label>
                <label className="flex items-center gap-2 p-2 bg-panel-bg border border-panel-border rounded-lg cursor-pointer hover:border-accent">
                  <input
                    type="checkbox"
                    checked={extractVmaps}
                    onChange={(e) => setExtractVmaps(e.target.checked)}
                    disabled={running}
                    className="accent-accent"
                  />
                  <span className="text-sm text-white">VMaps</span>
                  <span className="text-xs text-green-400 ml-auto">Required</span>
                </label>
                <label className="flex items-center gap-2 p-2 bg-panel-bg border border-panel-border rounded-lg cursor-pointer hover:border-accent">
                  <input
                    type="checkbox"
                    checked={generateMmaps}
                    onChange={(e) => setGenerateMmaps(e.target.checked)}
                    disabled={running}
                    className="accent-accent"
                  />
                  <span className="text-sm text-white">MMaps</span>
                  <span className="text-xs text-yellow-400 ml-auto">Optional</span>
                </label>
              </div>
              {generateMmaps && (
                <p className="text-xs text-yellow-400 mt-2">
                  ⚠️ MMaps generation takes 30-60 minutes. Consider using the download method instead.
                </p>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <Button
                variant="primary"
                icon={<HardDrive size={14} />}
                loading={running}
                disabled={running}
                onClick={startExtraction}
              >
                {running ? 'Extracting...' : 'Start Extraction'}
              </Button>
              {running && (
                <Button variant="danger" icon={<StopCircle size={14} />} onClick={cancel}>
                  Cancel
                </Button>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Progress Log */}
      {(logs.length > 0 || running || error) && (
        <Card>
          <CardHeader
            title="Progress Log"
            subtitle={running ? 'Operation in progress...' : 'Completed'}
            action={
              running && (
                <span className="text-xs text-accent animate-pulse">
                  {status?.current_step || 'Processing...'}
                </span>
              )
            }
          />
          <div className="bg-panel-bg border border-panel-border rounded-lg p-3 h-80 overflow-y-auto font-mono text-xs">
            {logs.map((line, i) => (
              <div
                key={i}
                className={
                  line.startsWith('[error]')
                    ? 'text-red-400'
                    : line.startsWith('[done]')
                    ? 'text-green-400'
                    : line.startsWith('[warning]')
                    ? 'text-yellow-400'
                    : line.startsWith('[step:')
                    ? 'text-accent font-semibold'
                    : 'text-panel-muted'
                }
              >
                {line}
              </div>
            ))}
            {error && <div className="text-red-400">Error: {error}</div>}
            <div ref={bottomRef} />
          </div>
        </Card>
      )}
    </div>
  )
}
