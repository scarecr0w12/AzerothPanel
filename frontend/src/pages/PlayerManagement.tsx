import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Ban, LogOut, MessageSquare, ChevronLeft, ChevronRight } from 'lucide-react'
import { playersApi } from '@/services/api'
import { Card, CardHeader } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { RACE_NAMES, CLASS_NAMES, CLASS_COLORS, ZONE_NAMES } from '@/types'
import type { Account, Character } from '@/types'

type Tab = 'accounts' | 'characters'

export default function PlayerManagement() {
  const [tab, setTab] = useState<Tab>('characters')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [banTarget, setBanTarget] = useState<Account | null>(null)
  const [banDuration, setBanDuration] = useState('1d')
  const [banReason, setBanReason] = useState('')
  const [announceMsg, setAnnounceMsg] = useState('')
  const qc = useQueryClient()

  const charQuery = useQuery({
    queryKey: ['characters', search, page],
    queryFn: () => playersApi.characters(search || undefined, false, page).then((r) => r.data),
    enabled: tab === 'characters',
  })

  const accQuery = useQuery({
    queryKey: ['accounts', search, page],
    queryFn: () => playersApi.accounts(search || undefined, page).then((r) => r.data),
    enabled: tab === 'accounts',
  })

  const kickMut = useMutation({
    mutationFn: (name: string) => playersApi.kick(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['characters'] }),
  })

  const banMut = useMutation({
    mutationFn: () => playersApi.ban(banTarget!.id, banDuration, banReason),
    onSuccess: () => { setBanTarget(null); qc.invalidateQueries({ queryKey: ['accounts'] }) },
  })

  const announceMut = useMutation({
    mutationFn: () => playersApi.announce(announceMsg),
    onSuccess: () => setAnnounceMsg(''),
  })

  const characters: Character[] = charQuery.data?.characters ?? []
  const accounts: Account[] = accQuery.data?.accounts ?? []
  const totalPages = tab === 'characters' ? (charQuery.data?.total_pages ?? 1) : (accQuery.data?.total_pages ?? 1)

  function handleSearch(val: string) { setSearch(val); setPage(1) }

  return (
    <div className="space-y-4">
      {/* Tab + Search bar */}
      <Card padding={false}>
        <div className="flex flex-wrap items-center gap-3 p-3">
          {(['characters', 'accounts'] as Tab[]).map((t) => (
            <button key={t} onClick={() => { setTab(t); setPage(1); setSearch('') }}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors ${tab === t ? 'bg-brand text-white' : 'text-panel-muted hover:text-white'}`}>
              {t}
            </button>
          ))}
          <div className="flex-1 flex items-center gap-2 bg-panel-bg border border-panel-border rounded-lg px-3 py-1.5 max-w-xs">
            <Search size={14} className="text-panel-muted shrink-0" />
            <input value={search} onChange={(e) => handleSearch(e.target.value)}
              placeholder={`Search ${tab}…`}
              className="bg-transparent text-sm text-white placeholder-panel-muted outline-none flex-1" />
          </div>
        </div>
      </Card>

      {/* Announce bar */}
      <Card padding={false}>
        <div className="flex items-center gap-2 p-3">
          <MessageSquare size={14} className="text-panel-muted shrink-0" />
          <input value={announceMsg} onChange={(e) => setAnnounceMsg(e.target.value)}
            placeholder="Server-wide announcement…"
            className="flex-1 bg-transparent text-sm text-white placeholder-panel-muted outline-none" />
          <Button size="sm" variant="secondary" loading={announceMut.isPending}
            disabled={!announceMsg.trim()} onClick={() => announceMut.mutate()}>Announce</Button>
        </div>
      </Card>

      {/* Characters table */}
      {tab === 'characters' && (
        <Card padding={false}>
          <CardHeader title="Characters" subtitle={`${characters.length} shown`} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-panel-border text-xs text-panel-muted uppercase">
                  {['Name', 'Race', 'Class', 'Level', 'Zone', 'Status', 'Actions'].map((h) => (
                    <th key={h} className="text-left px-4 py-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {charQuery.isLoading && (
                  <tr><td colSpan={7} className="text-center py-8 text-panel-muted">Loading…</td></tr>
                )}
                {characters.map((c) => (
                  <tr key={c.guid} className="border-b border-panel-border/50 hover:bg-panel-hover/30 transition-colors">
                    <td className="px-4 py-2.5 font-medium text-white">{c.name}</td>
                    <td className="px-4 py-2.5 text-panel-muted">{RACE_NAMES[c.race] ?? c.race}</td>
                    <td className="px-4 py-2.5">
                      <span style={{ color: CLASS_COLORS[c.class] }}>{CLASS_NAMES[c.class] ?? c.class}</span>
                    </td>
                    <td className="px-4 py-2.5 font-mono">{c.level}</td>
                    <td className="px-4 py-2.5 text-panel-muted">{ZONE_NAMES[c.zone] ?? c.zone}</td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs font-medium ${c.online ? 'text-success' : 'text-panel-muted'}`}>
                        {c.online ? '● Online' : '○ Offline'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {c.online && (
                        <Button variant="danger" size="sm" icon={<LogOut size={12} />}
                          loading={kickMut.isPending} onClick={() => kickMut.mutate(c.name)}>Kick</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={totalPages} onPage={setPage} />
        </Card>
      )}

      {/* Accounts table */}
      {tab === 'accounts' && (
        <Card padding={false}>
          <CardHeader title="Accounts" subtitle={`${accounts.length} shown`} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-panel-border text-xs text-panel-muted uppercase">
                  {['ID', 'Username', 'GM Level', 'Last IP', 'Status', 'Actions'].map((h) => (
                    <th key={h} className="text-left px-4 py-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {accQuery.isLoading && (
                  <tr><td colSpan={6} className="text-center py-8 text-panel-muted">Loading…</td></tr>
                )}
                {accounts.map((a) => (
                  <tr key={a.id} className="border-b border-panel-border/50 hover:bg-panel-hover/30 transition-colors">
                    <td className="px-4 py-2.5 font-mono text-panel-muted">{a.id}</td>
                    <td className="px-4 py-2.5 font-medium text-white">{a.username}</td>
                    <td className="px-4 py-2.5">{a.gmlevel > 0 ? <span className="text-brand-light text-xs font-medium">GM {a.gmlevel}</span> : <span className="text-panel-muted">Player</span>}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-panel-muted">{a.last_ip ?? '—'}</td>
                    <td className="px-4 py-2.5">
                      {a.banned
                        ? <span className="text-xs font-medium text-danger">● Banned</span>
                        : <span className="text-xs font-medium text-success">● Active</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      {!a.banned && (
                        <Button variant="danger" size="sm" icon={<Ban size={12} />}
                          onClick={() => setBanTarget(a)}>Ban</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={totalPages} onPage={setPage} />
        </Card>
      )}

      {/* Ban Modal */}
      {banTarget && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-panel-surface border border-panel-border rounded-2xl p-6 w-full max-w-md space-y-4">
            <h3 className="text-lg font-semibold text-white">Ban Account: {banTarget.username}</h3>
            <div className="space-y-3">
              <label className="block text-xs font-medium text-panel-muted uppercase tracking-wide">Duration</label>
              <select value={banDuration} onChange={(e) => setBanDuration(e.target.value)}
                className="w-full bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-white text-sm">
                {['1h','1d','7d','30d','-1'].map((d) => <option key={d} value={d}>{d === '-1' ? 'Permanent' : d}</option>)}
              </select>
              <label className="block text-xs font-medium text-panel-muted uppercase tracking-wide">Reason</label>
              <input value={banReason} onChange={(e) => setBanReason(e.target.value)}
                placeholder="Reason for ban…"
                className="w-full bg-panel-bg border border-panel-border rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-brand" />
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="secondary" onClick={() => setBanTarget(null)}>Cancel</Button>
              <Button variant="danger" loading={banMut.isPending} onClick={() => banMut.mutate()}>Confirm Ban</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Pagination({ page, total, onPage }: { page: number; total: number; onPage: (p: number) => void }) {
  if (total <= 1) return null
  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-panel-border text-sm">
      <span className="text-panel-muted">Page {page} of {total}</span>
      <div className="flex gap-2">
        <Button variant="ghost" size="sm" disabled={page === 1} icon={<ChevronLeft size={14} />} onClick={() => onPage(page - 1)} />
        <Button variant="ghost" size="sm" disabled={page === total} icon={<ChevronRight size={14} />} onClick={() => onPage(page + 1)} />
      </div>
    </div>
  )
}

