import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  FileText, Save, Loader2, CheckCircle, XCircle, AlertTriangle,
  Server, Package, RefreshCw,
} from 'lucide-react'
import { configsApi } from '@/services/api'

// ─── Types ────────────────────────────────────────────────────────────────────

interface ConfigFile {
  name: string
  label: string
  size_bytes: number
  is_module: boolean
}

interface ConfigListResponse {
  conf_dir: string
  files: ConfigFile[]
}

// ─── File list sidebar ────────────────────────────────────────────────────────

function FileItem({
  file,
  active,
  dirty,
  onClick,
}: {
  file: ConfigFile
  active: boolean
  dirty: boolean
  onClick: () => void
}) {
  const Icon = file.is_module ? Package : Server

  return (
    <button
      onClick={onClick}
      className={[
        'w-full text-left flex items-start gap-2.5 px-3 py-2.5 rounded-lg text-sm transition-colors',
        active
          ? 'bg-brand/20 text-white'
          : 'text-gray-400 hover:bg-panel-hover hover:text-white',
      ].join(' ')}
    >
      <Icon size={15} className={active ? 'text-brand-light shrink-0 mt-0.5' : 'shrink-0 mt-0.5'} />
      <span className="flex-1 min-w-0 truncate font-mono text-xs leading-5">
        {file.name}
      </span>
      {dirty && (
        <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5" title="Unsaved changes" />
      )}
    </button>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function ConfigEditor() {
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [savedContent, setSavedContent] = useState('')
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const isDirty = content !== savedContent

  // ── Fetch file list ───────────────────────────────────────────────────────

  const {
    data: listData,
    isLoading: listLoading,
    isError: listError,
    refetch: refetchList,
  } = useQuery<ConfigListResponse>({
    queryKey: ['config-list'],
    queryFn: async () => {
      const res = await configsApi.list()
      return res.data as ConfigListResponse
    },
  })

  // Auto-select first file when list loads
  useEffect(() => {
    if (listData?.files?.length && !selectedFile) {
      setSelectedFile(listData.files[0].name)
    }
  }, [listData, selectedFile])

  // ── Fetch file content ────────────────────────────────────────────────────

  const {
    isFetching: contentLoading,
    isError: contentError,
  } = useQuery({
    queryKey: ['config-content', selectedFile],
    queryFn: async () => {
      if (!selectedFile) return null
      const res = await configsApi.get(selectedFile)
      const text: string = res.data.content ?? ''
      setContent(text)
      setSavedContent(text)
      setSaveMsg(null)
      return res.data
    },
    enabled: !!selectedFile,
  })

  // ── Save ──────────────────────────────────────────────────────────────────

  const saveMutation = useMutation({
    mutationFn: () => configsApi.save(selectedFile!, content),
    onSuccess: () => {
      setSavedContent(content)
      setSaveMsg({ ok: true, text: 'Saved successfully.' })
      setTimeout(() => setSaveMsg(null), 4000)
    },
    onError: (e: unknown) => {
      const msg = e instanceof Error ? e.message : 'Save failed.'
      setSaveMsg({ ok: false, text: msg })
    },
  })

  // ── keyboard shortcut Ctrl+S ──────────────────────────────────────────────

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's' && selectedFile && isDirty) {
        e.preventDefault()
        saveMutation.mutate()
      }
    },
    [selectedFile, isDirty, saveMutation],
  )

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // ── Split files into core / modules ──────────────────────────────────────

  const coreFiles = listData?.files.filter(f => !f.is_module) ?? []
  const moduleFiles = listData?.files.filter(f => f.is_module) ?? []

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* ── Left: file list ── */}
      <aside className="flex flex-col w-56 shrink-0 border-r border-panel-border bg-panel-surface overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-panel-border">
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-brand-light" />
            <span className="text-sm font-semibold text-white">Config Files</span>
          </div>
          <button
            onClick={() => refetchList()}
            className="p-1 rounded text-panel-muted hover:text-white hover:bg-panel-hover transition-colors"
            title="Refresh"
          >
            <RefreshCw size={13} />
          </button>
        </div>

        {listLoading && (
          <div className="flex items-center justify-center flex-1 text-panel-muted text-sm gap-2">
            <Loader2 size={16} className="animate-spin" /> Loading…
          </div>
        )}

        {listError && (
          <div className="p-4 text-xs text-danger">
            Failed to load config files.
          </div>
        )}

        {!listLoading && !listError && listData && (
          <nav className="flex-1 p-2 space-y-4">
            {/* Core configs */}
            {coreFiles.length > 0 && (
              <div>
                <p className="px-2 mb-1 text-xs font-semibold uppercase tracking-wide text-panel-muted">
                  Core
                </p>
                <div className="space-y-0.5">
                  {coreFiles.map(f => (
                    <FileItem
                      key={f.name}
                      file={f}
                      active={selectedFile === f.name}
                      dirty={selectedFile === f.name && isDirty}
                      onClick={() => {
                        if (selectedFile !== f.name) setSelectedFile(f.name)
                      }}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Module configs */}
            {moduleFiles.length > 0 && (
              <div>
                <p className="px-2 mb-1 text-xs font-semibold uppercase tracking-wide text-panel-muted">
                  Modules
                </p>
                <div className="space-y-0.5">
                  {moduleFiles.map(f => (
                    <FileItem
                      key={f.name}
                      file={f}
                      active={selectedFile === f.name}
                      dirty={selectedFile === f.name && isDirty}
                      onClick={() => {
                        if (selectedFile !== f.name) setSelectedFile(f.name)
                      }}
                    />
                  ))}
                </div>
              </div>
            )}

            {listData.files.length === 0 && (
              <div className="px-2 py-4 text-xs text-panel-muted">
                No .conf files found in:
                <br />
                <span className="font-mono text-white break-all">{listData.conf_dir}</span>
              </div>
            )}
          </nav>
        )}

        {/* conf_dir info */}
        {listData && (
          <div className="px-3 py-2 border-t border-panel-border text-xs text-panel-muted font-mono break-all">
            {listData.conf_dir}
          </div>
        )}
      </aside>

      {/* ── Right: editor ── */}
      <div className="flex flex-col flex-1 min-w-0 bg-panel-bg">
        {/* Toolbar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-panel-border bg-panel-surface shrink-0">
          {selectedFile ? (
            <>
              <span className="font-mono text-sm text-white">{selectedFile}</span>
              {isDirty && (
                <span className="text-xs text-amber-400 flex items-center gap-1">
                  <AlertTriangle size={12} /> Unsaved changes
                </span>
              )}
              {saveMsg && (
                saveMsg.ok
                  ? <span className="text-xs text-success flex items-center gap-1"><CheckCircle size={12} />{saveMsg.text}</span>
                  : <span className="text-xs text-danger flex items-center gap-1"><XCircle size={12} />{saveMsg.text}</span>
              )}
            </>
          ) : (
            <span className="text-sm text-panel-muted">Select a file to edit</span>
          )}

          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-panel-muted hidden sm:block">Ctrl+S to save</span>
            <button
              onClick={() => saveMutation.mutate()}
              disabled={!selectedFile || !isDirty || saveMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                         bg-brand text-white hover:bg-brand/90 disabled:opacity-40 disabled:cursor-not-allowed
                         transition-colors"
            >
              {saveMutation.isPending
                ? <Loader2 size={12} className="animate-spin" />
                : <Save size={12} />}
              Save
            </button>
          </div>
        </div>

        {/* Editor area */}
        {!selectedFile && (
          <div className="flex flex-col items-center justify-center flex-1 text-panel-muted gap-3">
            <FileText size={40} strokeWidth={1.5} />
            <p className="text-sm">Select a config file from the sidebar</p>
          </div>
        )}

        {selectedFile && contentLoading && (
          <div className="flex items-center justify-center flex-1 text-panel-muted gap-2">
            <Loader2 size={20} className="animate-spin" /> Loading…
          </div>
        )}

        {selectedFile && contentError && (
          <div className="flex items-center justify-center flex-1 gap-2 text-danger text-sm">
            <XCircle size={18} /> Failed to load file content.
          </div>
        )}

        {selectedFile && !contentLoading && !contentError && (
          <textarea
            className="flex-1 w-full bg-transparent p-4 font-mono text-xs text-gray-200
                       resize-none border-none outline-none leading-relaxed
                       placeholder-panel-muted caret-brand"
            value={content}
            onChange={e => setContent(e.target.value)}
            spellCheck={false}
            autoCorrect="off"
            autoCapitalize="off"
            placeholder="File is empty."
          />
        )}
      </div>
    </div>
  )
}
