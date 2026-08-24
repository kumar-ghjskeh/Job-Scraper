import { useEffect, useState } from 'react'
import { loadCorpus } from '../lib/corpus'
import { parseApiDate } from '../lib/datetime'
import type { Company } from '../lib/types'
import { CompanyLogo } from './CompanyLogo'
import { Icon } from './Icon'

function priorityColor(p: string): { bg: string; color: string } {
  switch (p) {
    case 'S': return { bg: '#FEF3C7', color: '#B45309' }
    case 'A': return { bg: '#DBEAFE', color: '#1D4ED8' }
    case 'B': return { bg: '#CFFAFE', color: '#0891B2' }
    default:  return { bg: '#F3F4F6', color: '#6B7280' }
  }
}

function statusDot(co: Company) {
  // Judged on what the source is actually producing in the current snapshot.
  // This used to key off last_scraped_at, which a rebuilt corpus never stamps —
  // so every company rendered as "Never scraped" even while returning jobs.
  if (co.scrape_status === 'error' || co.scrape_error_count > 2) {
    return { color: 'var(--danger)', label: 'Errors' }
  }
  const live = co.total_active_jobs ?? 0
  const usable = co.viewable_jobs ?? 0
  if (live > 0 && usable > 0) return { color: 'var(--success)', label: 'Live' }
  if (live > 0) return { color: 'var(--teal)', label: 'Live · no US roles' }
  return { color: '#9CA3AF', label: 'No openings' }
}

const ATS_COLORS: Record<string, { bg: string; color: string }> = {
  greenhouse: { bg: '#DCFCE7', color: '#166534' },
  lever:      { bg: '#DBEAFE', color: '#1E40AF' },
  ashby:      { bg: '#E0F5F9', color: '#0E7490' },
  workday:    { bg: '#FEF3C7', color: '#92400E' },
  amazon:     { bg: '#FFF7ED', color: '#C2410C' },
  apple:      { bg: '#F3F4F6', color: '#374151' },
  google:     { bg: '#FEF9C3', color: '#713F12' },
  microsoft:  { bg: '#DBEAFE', color: '#1D4ED8' },
  meta:       { bg: '#EFF6FF', color: '#1D4ED8' },
  generic:    { bg: '#F3F4F6', color: '#6B7280' },
}

interface Props {
  onViewJobs?: (companyName: string) => void
}

// Module-level cache so re-opening the Companies tab paints instantly while it
// refreshes in the background (survives tab switches within a session).
let _companiesCache: Company[] | null = null

export function CompaniesPage({ onViewJobs }: Props) {
  const [companies, setCompanies] = useState<Company[]>(() => _companiesCache ?? [])
  const [loading, setLoading] = useState(() => _companiesCache === null)
  const [search, setSearch] = useState('')
  const [filterPriority, setFilterPriority] = useState('')

  useEffect(() => {
    // Companies come from the static snapshot (sourced from the YAML config and
    // tallied over the published corpus) — same data the endpoint returned.
    loadCorpus().then((corpus) => {
      const data = corpus.companies.map((c, i) => ({
        id: i + 1, name: c.name, category: c.category, priority: c.priority,
        careers_url: c.careers_url, company_search_url: '', ats_platform: c.ats_platform,
        enabled: c.enabled, last_scraped_at: c.last_scraped_at,
        scrape_error_count: c.scrape_error_count, notes: '',
        total_active_jobs: c.total_active_jobs, usa_active_jobs: c.usa_active_jobs,
        viewable_jobs: c.viewable_jobs, entry_level_jobs: c.entry_level_jobs,
        new_jobs_today: c.new_jobs_today, parser_confidence: c.parser_confidence,
        scrape_status: c.scrape_status, engine: c.engine,
        auto_connected: c.auto_connected,
        })) as unknown as Company[]
      return data
    }).then((data) => {
      _companiesCache = data
      setCompanies(data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const filtered = companies.filter((co) => {
    if (search && !co.name.toLowerCase().includes(search.toLowerCase()) &&
        !co.category.toLowerCase().includes(search.toLowerCase())) return false
    if (filterPriority && co.priority !== filterPriority) return false
    return true
  })

  const byPriority = ['S', 'A', 'B', 'C']
  const grouped: Record<string, Company[]> = {}
  for (const p of byPriority) {
    grouped[p] = filtered.filter((c) => c.priority === p)
  }

  const fmtDate = (d: string | null) => {
    const date = parseApiDate(d)
    return date ? date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Never'
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading companies...
      </div>
    )
  }

  return (
    <div>
      {/* Header + controls */}
      <div style={{
        display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap',
      }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text)', flex: 1 }}>
          Company Directory
          <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>
            {filtered.length} companies
          </span>
        </h2>

        <input
          placeholder="Search companies..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            border: '1px solid var(--border)', borderRadius: 8,
            padding: '7px 12px', fontSize: 13, width: 220,
            background: 'var(--surface)', color: 'var(--text)', outline: 'none',
          }}
        />

        <div style={{ display: 'flex', gap: 4 }}>
          {['', 'S', 'A', 'B', 'C'].map((p) => (
            <button
              key={p}
              onClick={() => setFilterPriority(p)}
              style={{
                background: filterPriority === p ? 'var(--primary)' : 'var(--surface)',
                border: `1px solid ${filterPriority === p ? 'var(--primary)' : 'var(--border)'}`,
                borderRadius: 6, padding: '5px 10px', fontSize: 12,
                fontWeight: 600, cursor: 'pointer',
                color: filterPriority === p ? '#fff' : 'var(--text-muted)',
              }}
            >
              {p || 'All'}
            </button>
          ))}
        </div>
      </div>

      {/* Coverage at a glance. The directory previously gave no way to tell which
          sources were actually feeding the board — every card looked the same
          whether it was producing 97 roles or none. */}
      {(() => {
        const live = companies.filter((c) => (c.total_active_jobs ?? 0) > 0)
        const withUs = companies.filter((c) => (c.viewable_jobs ?? 0) > 0)
        const tracked = companies.filter((c) => c.enabled)
        const usRoles = companies.reduce((n, c) => n + (c.viewable_jobs ?? 0), 0)
        const erroring = companies.filter((c) => (c.scrape_error_count ?? 0) > 2)
        const cards: { label: string; value: string; color: string; hint: string }[] = [
          { label: 'Feeding the board', value: `${withUs.length}`, color: 'var(--success)',
            hint: `${withUs.length} companies are returning US roles right now` },
          { label: 'Connected sources', value: `${live.length}/${tracked.length}`, color: 'var(--primary)',
            hint: `${live.length} of ${tracked.length} tracked companies returned postings on the last scrape` },
          { label: 'US roles listed', value: usRoles.toLocaleString(), color: 'var(--teal)',
            hint: 'Total US, hardware-relevant roles across every company' },
          { label: 'Sources with errors', value: `${erroring.length}`,
            color: erroring.length ? 'var(--danger)' : 'var(--success)',
            hint: erroring.length ? 'These need a scraper fix' : 'No source is failing' },
        ]
        return (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 18 }}>
            {cards.map((c) => (
              <div key={c.label} title={c.hint} style={{
                flex: '1 1 150px', background: 'var(--surface)',
                border: '1px solid var(--border)', borderLeft: `3px solid ${c.color}`,
                borderRadius: 10, padding: '10px 14px', minWidth: 140,
              }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: c.color, lineHeight: 1.1 }}>{c.value}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, fontWeight: 600 }}>{c.label}</div>
              </div>
            ))}
          </div>
        )
      })()}

      {byPriority.filter((p) => grouped[p]?.length > 0).map((priority) => {
        const pri = priorityColor(priority)
        const tierLabels: Record<string, string> = {
          S: 'S-Tier — Dream Companies',
          A: 'A-Tier — Primary Targets',
          B: 'B-Tier — Good Options',
          C: 'C-Tier — Backup Options',
        }
        return (
          <div key={priority} style={{ marginBottom: 24 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
            }}>
              <span style={{
                background: pri.bg, color: pri.color,
                fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 5,
              }}>
                {priority}
              </span>
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
                {tierLabels[priority]}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                ({grouped[priority].length})
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 8 }}>
              {grouped[priority].map((co) => {
                const dot = statusDot(co)
                const atsStyle = ATS_COLORS[co.ats_platform] || ATS_COLORS.generic
                const connected = (co.total_active_jobs ?? 0) > 0
                return (
                  <div key={co.id} style={{
                    background: 'var(--surface)',
                    // Connected sources get a tinted edge so the directory reads
                    // at a glance instead of needing the label to be parsed.
                    border: `1px solid ${connected ? 'var(--success-border)' : 'var(--border)'}`,
                    borderLeft: `3px solid ${connected ? dot.color : 'var(--border-strong)'}`,
                    borderRadius: 10, padding: '12px 14px',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flex: 1, minWidth: 0 }}>
                        <CompanyLogo company={co.name} size={38} radius={9} />
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>{co.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{co.category}</div>
                        </div>
                      </div>
                      {connected ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                          <span style={{
                            width: 9, height: 9, borderRadius: '50%', background: dot.color,
                            boxShadow: dot.label === 'Live' ? '0 0 0 3px rgba(34,197,94,0.18)' : 'none',
                          }} title={dot.label} />
                          <span style={{ fontSize: 10.5, fontWeight: 700, color: dot.color }}>{dot.label}</span>
                        </div>
                      ) : (
                        <span className="pill pill-neutral" style={{ flexShrink: 0 }}
                          title="Tracked, but no live openings matched right now">
                          No openings
                        </span>
                      )}
                    </div>

                    {connected ? (
                      <>
                        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                          <span style={{ background: atsStyle.bg, color: atsStyle.color, fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4, textTransform: 'capitalize' }}>{co.ats_platform}</span>
                          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{co.total_active_jobs} scanned</span>
                          {(co.viewable_jobs ?? 0) > 0 && <span style={{ fontSize: 11, color: 'var(--success)', fontWeight: 700 }}>{co.viewable_jobs} US roles</span>}
                          {(co.entry_level_jobs ?? 0) > 0 && <span style={{ fontSize: 11, color: 'var(--teal)', fontWeight: 600 }}>{co.entry_level_jobs} entry-lvl</span>}
                          {(co.new_jobs_today ?? 0) > 0 && <span style={{ fontSize: 11, color: 'var(--primary)', fontWeight: 600 }}>{co.new_jobs_today} new today</span>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Last updated: {fmtDate(co.last_scraped_at)}</span>
                          {(co.total_active_jobs ?? 0) > 0 && co.parser_confidence !== undefined && (() => {
                            const pc = co.parser_confidence!
                            const c = pc >= 80 ? 'var(--success)' : pc >= 60 ? 'var(--teal)' : pc >= 40 ? 'var(--warning)' : 'var(--danger)'
                            return (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }} title="Average data-quality of parsed postings">
                                <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>·</span>
                                <span style={{ width: 42, height: 5, background: 'var(--surface-muted)', borderRadius: 3, overflow: 'hidden', display: 'inline-block' }}>
                                  <span style={{ display: 'block', width: `${pc}%`, height: '100%', background: c, borderRadius: 3 }} />
                                </span>
                                <span style={{ fontSize: 11, color: c, fontWeight: 700 }}>{pc}% parser</span>
                              </span>
                            )
                          })()}
                        </div>
                      </>
                    ) : (
                      <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginTop: 8, lineHeight: 1.5 }}>
                        {co.enabled
                          ? 'Connected, but no matching openings right now — search their careers site directly.'
                          : 'Not auto-connected — search openings directly on their careers site.'}
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                      {connected && onViewJobs && (co.viewable_jobs ?? co.total_active_jobs ?? 0) > 0 && (
                        <button onClick={() => onViewJobs(co.name)} className="btn btn-primary" style={{ padding: '5px 12px', fontSize: 12 }}>
                          View {co.viewable_jobs ?? co.total_active_jobs} Jobs
                        </button>
                      )}
                      {(co.company_search_url || co.careers_url) && (
                        <a href={co.company_search_url || co.careers_url} target="_blank" rel="noopener noreferrer"
                          className={connected ? '' : 'btn btn-outline'}
                          style={connected ? { fontSize: 12, color: 'var(--primary)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4 } : { padding: '5px 12px', fontSize: 12 }}>
                          Search Jobs <Icon name="external" size={12} color={connected ? 'var(--primary)' : 'var(--primary)'} />
                        </a>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
