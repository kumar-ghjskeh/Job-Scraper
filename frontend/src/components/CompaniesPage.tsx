import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Company } from '../lib/types'

function priorityColor(p: string): { bg: string; color: string } {
  switch (p) {
    case 'S': return { bg: '#FEF3C7', color: '#B45309' }
    case 'A': return { bg: '#DBEAFE', color: '#1D4ED8' }
    case 'B': return { bg: '#CFFAFE', color: '#0891B2' }
    default:  return { bg: '#F3F4F6', color: '#6B7280' }
  }
}

function statusDot(co: Company) {
  if (!co.last_scraped_at) return { color: '#9CA3AF', label: 'Never scraped' }
  const minsAgo = (Date.now() - new Date(co.last_scraped_at).getTime()) / 60000
  if (co.scrape_status === 'error' || co.scrape_error_count > 2) return { color: '#DC2626', label: 'Errors' }
  if (minsAgo < 360) return { color: '#16A34A', label: 'Fresh' }
  if (minsAgo < 1440) return { color: '#D97706', label: 'Stale' }
  return { color: '#9CA3AF', label: 'Old' }
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

export function CompaniesPage({ onViewJobs }: Props) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterPriority, setFilterPriority] = useState('')

  useEffect(() => {
    api.getCompanies().then((data) => {
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

  const fmtDate = (d: string | null) => d
    ? new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Never'

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
                return (
                  <div key={co.id} style={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 10, padding: '12px 14px',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>
                          {co.name}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                          {co.category}
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <div style={{
                          width: 8, height: 8, borderRadius: '50%', background: dot.color,
                        }} title={dot.label} />
                        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{dot.label}</span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                      <span style={{
                        background: atsStyle.bg, color: atsStyle.color,
                        fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                        textTransform: 'capitalize',
                      }}>
                        {co.ats_platform}
                      </span>

                      {co.total_active_jobs !== undefined && (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {co.total_active_jobs} total
                        </span>
                      )}
                      {co.viewable_jobs !== undefined && co.viewable_jobs > 0 && (
                        <span style={{ fontSize: 11, color: 'var(--text)', fontWeight: 600 }}>
                          {co.viewable_jobs} USA/relevant
                        </span>
                      )}
                      {co.entry_level_jobs !== undefined && co.entry_level_jobs > 0 && (
                        <span style={{ fontSize: 11, color: 'var(--teal)', fontWeight: 600 }}>
                          {co.entry_level_jobs} entry-lvl
                        </span>
                      )}
                      {co.new_jobs_today !== undefined && co.new_jobs_today > 0 && (
                        <span style={{ fontSize: 11, color: 'var(--primary)', fontWeight: 600 }}>
                          {co.new_jobs_today} new today
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6 }}>
                      Last scraped: {fmtDate(co.last_scraped_at)}
                      {co.scrape_error_count > 0 && (
                        <span style={{ color: 'var(--error)', marginLeft: 6 }}>
                          {co.scrape_error_count} errors
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                      {onViewJobs && (co.viewable_jobs ?? co.total_active_jobs ?? 0) > 0 && (
                        <button
                          onClick={() => onViewJobs(co.name)}
                          style={{
                            background: 'var(--primary)', color: '#fff',
                            border: 'none', borderRadius: 6, padding: '5px 12px',
                            fontSize: 12, fontWeight: 600, cursor: 'pointer',
                          }}
                        >
                          View {co.viewable_jobs ?? co.total_active_jobs} Jobs →
                        </button>
                      )}
                      <a
                        href={co.company_search_url || co.careers_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: 11, color: 'var(--primary)' }}
                      >
                        Search Jobs
                      </a>
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
