import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Play, Download, ChevronLeft, ChevronRight, Database } from 'lucide-react'
import { dbApi } from '@/services/api'
import { Card, CardHeader } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import type { DatabaseTarget, QueryResult } from '@/types'

const DATABASES: { value: DatabaseTarget; label: string; color: string }[] = [
  { value: 'auth',       label: 'Auth',       color: 'text-blue-400' },
  { value: 'characters', label: 'Characters', color: 'text-yellow-400' },
  { value: 'world',      label: 'World',      color: 'text-green-400' },
]

export default function DatabaseManager() {
  const [db, setDb] = useState<DatabaseTarget>('characters')
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [sql, setSql] = useState('')
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null)
  const [queryError, setQueryError] = useState<string | null>(null)
  const [browsePage, setBrowsePage] = useState(1)

  const tablesQuery = useQuery({
    queryKey: ['db-tables', db],
    queryFn: () => dbApi.tables(db).then((r) => r.data.tables as string[]),
  })

  const browseQuery = useQuery({
    queryKey: ['db-browse', db, selectedTable, browsePage],
    queryFn: () => dbApi.browse(db, selectedTable!, browsePage).then((r) => r.data as QueryResult),
    enabled: !!selectedTable,
  })

  const queryMut = useMutation({
    mutationFn: () => dbApi.query(db, sql).then((r) => r.data as QueryResult),
    onSuccess: (data) => { setQueryResult(data); setQueryError(null) },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      setQueryError(err.response?.data?.detail ?? 'Query failed')
      setQueryResult(null)
    },
  })

  const backupMut = useMutation({
    mutationFn: () => dbApi.backup(db),
  })

  const displayResult: QueryResult | null = selectedTable && !sql.trim() ? (browseQuery.data ?? null) : queryResult
  const tables: string[] = tablesQuery.data ?? []

  function handleTableClick(t: string) {
    setSelectedTable(t)
    setSql('')
    setQueryResult(null)
    setQueryError(null)
    setBrowsePage(1)
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-10rem)]">
      {/* Sidebar: database & table list */}
      <Card className="w-56 shrink-0 overflow-hidden flex flex-col" padding={false}>
        {/* DB selector */}
        <div className="p-3 border-b border-panel-border space-y-1">
          {DATABASES.map((d) => (
            <button key={d.value} onClick={() => { setDb(d.value); setSelectedTable(null); setQueryResult(null) }}
              className={`flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm transition-colors ${
                db === d.value ? 'bg-brand/20 text-brand-light' : 'text-panel-muted hover:text-white hover:bg-panel-hover'
              }`}>
              <Database size={14} className={db === d.value ? 'text-brand' : d.color} />
              {d.label}
            </button>
          ))}
        </div>

        {/* Table list */}
        <div className="flex-1 overflow-y-auto p-2">
          {tablesQuery.isLoading && <p className="text-xs text-panel-muted p-2">Loading tables…</p>}
          {tablesQuery.isError && (
            <p className="text-xs text-danger p-2">DB connection error — check Settings</p>
          )}
          {tables.map((t) => (
            <button key={t} onClick={() => handleTableClick(t)}
              className={`w-full text-left px-3 py-1.5 rounded text-xs font-mono transition-colors ${
                selectedTable === t ? 'bg-brand/20 text-brand-light' : 'text-panel-muted hover:text-white hover:bg-panel-hover'
              }`}>
              {t}
            </button>
          ))}
        </div>

        <div className="p-3 border-t border-panel-border">
          <Button variant="secondary" size="sm" icon={<Download size={13} />}
            loading={backupMut.isPending} onClick={() => backupMut.mutate()} className="w-full">
            Backup DB
          </Button>
          {backupMut.isSuccess && (
            <p className="text-xs text-success mt-1.5 text-center">Backup created ✓</p>
          )}
        </div>
      </Card>

      {/* Main panel */}
      <div className="flex-1 flex flex-col gap-4 min-w-0 overflow-hidden">
        {/* SQL editor */}
        <Card padding={false}>
          <CardHeader title="SQL Query Editor"
            subtitle={`Executing against: ${db}`}
            action={
              <Button size="sm" icon={<Play size={13} />}
                loading={queryMut.isPending} disabled={!sql.trim()}
                onClick={() => queryMut.mutate()}>
                Run Query
              </Button>
            }
          />
          <textarea
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) queryMut.mutate() }}
            placeholder={`SELECT * FROM characters LIMIT 10;\n-- Ctrl+Enter to execute`}
            rows={5}
            spellCheck={false}
            className="w-full bg-panel-bg font-mono text-xs text-green-300 border-t border-panel-border px-4 py-3 outline-none resize-none placeholder-panel-muted"
          />
          {queryError && (
            <div className="mx-4 mb-3 bg-danger/10 border border-danger/30 text-danger text-xs rounded-lg px-3 py-2">
              {queryError}
            </div>
          )}
        </Card>

        {/* Results / Browse */}
        <Card padding={false} className="flex-1 overflow-hidden flex flex-col">
          <CardHeader
            title={selectedTable && !sql.trim() ? `Browsing: ${selectedTable}` : 'Query Results'}
            subtitle={displayResult
              ? `${displayResult.total != null ? displayResult.total + ' total' : displayResult.row_count + ' rows'} · ${displayResult.execution_time_ms?.toFixed(1) ?? '?'}ms`
              : undefined}
          />
          <div className="flex-1 overflow-auto">
            {(browseQuery.isLoading && selectedTable && !sql.trim()) && (
              <p className="text-center text-panel-muted py-8">Loading…</p>
            )}
            {(browseQuery.isError && selectedTable && !sql.trim()) && (
              <p className="text-center text-danger py-8 text-sm">Failed to load table data — check Settings for DB credentials</p>
            )}
            {displayResult && displayResult.columns.length > 0 && (
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-panel-surface">
                  <tr className="border-b border-panel-border">
                    {displayResult.columns.map((col) => (
                      <th key={col} className="text-left px-3 py-2 text-panel-muted font-medium whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayResult.rows.map((row, i) => (
                    <tr key={i} className="border-b border-panel-border/40 hover:bg-panel-hover/30">
                      {(row as unknown[]).map((cell, j) => (
                        <td key={j} className="px-3 py-2 font-mono text-gray-300 max-w-xs truncate">
                          {cell === null ? <span className="text-panel-muted italic">NULL</span> : String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {displayResult && displayResult.columns.length === 0 && (
              <p className="text-center text-success py-8 text-sm">
                ✓ Query executed — {displayResult.row_count} rows affected
              </p>
            )}
            {!displayResult && !browseQuery.isLoading && (
              <p className="text-center text-panel-muted py-8 text-sm">
                Select a table or run a query to see results
              </p>
            )}
          </div>

          {/* Browse pagination */}
          {selectedTable && !sql.trim() && browseQuery.data && (
            <div className="flex items-center justify-between px-4 py-2 border-t border-panel-border">
              <span className="text-xs text-panel-muted">Page {browsePage}</span>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" disabled={browsePage === 1}
                  icon={<ChevronLeft size={14} />} onClick={() => setBrowsePage((p) => p - 1)} />
                <Button variant="ghost" size="sm"
                  disabled={!browseQuery.data || (browsePage * (browseQuery.data.page_size ?? 50)) >= (browseQuery.data.total ?? 0)}
                  icon={<ChevronRight size={14} />} onClick={() => setBrowsePage((p) => p + 1)} />
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

