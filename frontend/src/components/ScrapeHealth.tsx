import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { parseApiDate } from '../lib/datetime'
import type { AnalyticsSummary, Company, ScrapeRun } from '../lib/types'

const TZ_OPTIONS: { label: string; value: string }[] = [
  { label: 'My local time', value: 'local' },
  { label: 'Eastern (ET)', value: 'America/New_York' },
  { label: 'Central (CT)', value: 'America/Chicago' },
  { label: 'Mountain (MT)', value: 'America/Denver' },
  { label: 'Pacific (PT)', value: 'America/Los_Angeles' },
]
const RUNS_PREVIEW = 20

// Module-level cache so re-opening Data Health paints instantly while it
// refreshes in the background (survives tab switches within a session).
let _healthCache: { runs: ScrapeRun[]; companies: Company[]; analytics: AnalyticsSummary | null } | null = null

export function ScrapeHealth() {
  const [runs, setRuns] = useState<ScrapeRun[]>(() => _healthCache?.runs ?? [])
  const [companies, setCompanies] = useState<Company[]>(() => _healthCache?.companies ?? [])
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(() => _healthCache?.analytics ?? null)
  const [loading, setLoading] = useState(() => _healthCache === null)
  const [tz, setTz] = useState<string>(() => localStorage.getItem('ashborne-tz') || 'local')
  const [showAllRuns, setShowAllRuns] = useState(false)

  useEffect(() => {
    Promise.all([api.getScrapeRuns(), api.getCompanies(), api.getAnalytics().catch(() => null)])
      .then(([r, c, a]) => { _healthCache = { runs: r, companies: c, analytics: a }; setRuns(r); setCompanies(c); setAnalytics(a) })
      .finally(() => setLoading(false))
  }, [])

  function changeTz(v: string) { setTz(v); localStorage.setItem('ashborne-tz', v) }

  const fmt = (d: string | null) => {
    const date = parseApiDate(d)
    if (!date) return '—'
    const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }
    if (tz !== 'local') opts.timeZone = tz
    return date.toLocaleString('en-US', opts)
  }

  const shownRuns = showAllRuns ? runs : runs.slice(0, RUNS_PREVIEW)

  const errCompanies = companies.filter((c) => c.scrape_error_count > 0)
    .sort((a, b) => b.scrape_error_count - a.scrape_error_count)

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div>
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text)' }}>
          Data Health
        </h2>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: 'var(--text-secondary)' }}>
          Times in
          <select value={tz} onChange={(e) => changeTz(e.target.value)}
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 7, padding: '5px 9px', color: 'var(--text-primary)', fontSize: 12.5, outline: 'none' }}>
            {TZ_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      </div>

      {/* Summary stats */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        {[
          { label: 'Total Runs', value: runs.length, color: 'var(--primary)' },
          { label: 'Auto-Connected', value: companies.filter(c => c.auto_connected ?? c.enabled).length, color: 'var(--success)' },
          { label: 'Companies with Errors', value: errCompanies.length, color: errCompanies.length > 0 ? 'var(--error)' : 'var(--success)' },
          { label: 'Last Run New Jobs', value: runs[0]?.new_jobs ?? 0, color: 'var(--teal)' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 10, padding: '12px 16px', minWidth: 130,
          }}>
            <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Job inventory funnel — reconciles "Found" (postings scanned) with the
          USA-relevant count shown on the dashboard so the numbers aren't confusing. */}
      {analytics?.job_inventory && (() => {
        const inv = analytics.job_inventory!
        const steps = [
          { label: 'Tracked in database', value: inv.active, color: 'var(--primary)',
            note: `${inv.total_in_db} total ever scraped` },
          { label: 'Filtered out', value: inv.non_usa_filtered + inv.software_filtered, color: 'var(--warning)',
            note: `${inv.non_usa_filtered} outside the US · ${inv.software_filtered} software-only` },
          { label: 'Shown to you', value: inv.usa_relevant, color: 'var(--success)',
            note: 'US-based / remote-US hardware roles — matches the All Jobs count' },
        ]
        return (
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 4px', color: 'var(--text)' }}>
              Job Inventory
            </h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px' }}>
              Why “Found” below is larger than the dashboard count: the scraper scans every posting,
              then keeps only US-based hardware roles for you.
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'stretch' }}>
              {steps.map((st, i) => (
                <div key={st.label} style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
                  <div style={{
                    background: 'var(--surface)', border: '1px solid var(--border)',
                    borderRadius: 10, padding: '12px 16px', minWidth: 150, maxWidth: 220,
                  }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: st.color }}>{st.value}</div>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text)', marginTop: 2 }}>{st.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.35 }}>{st.note}</div>
                  </div>
                  {i < steps.length - 1 && (
                    <div style={{ alignSelf: 'center', color: 'var(--text-faint)', fontSize: 18 }}>→</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Recent runs */}
      <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 4px', color: 'var(--text)' }}>
        Recent Scrape Runs
      </h3>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px' }}>
        “Found” = total postings scanned that run (before US / hardware filtering), not jobs added.
      </p>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 10, overflow: 'hidden', marginBottom: 24,
      }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
                {['Started', 'Duration', 'Companies', 'Found', 'New', 'Removed', 'Errors', 'By'].map((h) => (
                  <th key={h} style={{
                    padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)',
                    fontWeight: 700, fontSize: 11, letterSpacing: '0.04em', textTransform: 'uppercase',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No scrape runs yet. Click "Run Scrape" to start.
                  </td>
                </tr>
              ) : shownRuns.map((r) => {
                const dur = r.finished_at
                  ? Math.round((new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 60000)
                  : null
                return (
                  <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={td}>{fmt(r.started_at)}</td>
                    <td style={td}>{dur != null ? `${dur}m` : <span style={{ color: 'var(--warning)' }}>running</span>}</td>
                    <td style={td}>{r.companies_scraped}</td>
                    <td style={td}>{r.jobs_found}</td>
                    <td style={{ ...td, color: r.new_jobs > 0 ? 'var(--success)' : 'var(--text-muted)', fontWeight: r.new_jobs > 0 ? 600 : 400 }}>
                      {r.new_jobs > 0 ? `+${r.new_jobs}` : r.new_jobs}
                    </td>
                    <td style={{ ...td, color: r.removed_jobs > 0 ? 'var(--warning)' : 'var(--text-muted)' }}>
                      {r.removed_jobs ?? 0}
                    </td>
                    <td style={{ ...td, color: r.errors > 0 ? 'var(--error)' : 'var(--success)', fontWeight: r.errors > 0 ? 600 : 400 }}>
                      {r.errors}
                    </td>
                    <td style={{ ...td, color: 'var(--text-muted)', fontSize: 11 }}>{r.triggered_by}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {runs.length > RUNS_PREVIEW && (
          <div style={{ borderTop: '1px solid var(--border)', textAlign: 'center', padding: '8px' }}>
            <button onClick={() => setShowAllRuns((s) => !s)}
              style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: 12.5, fontWeight: 700, cursor: 'pointer' }}>
              {showAllRuns ? 'Show fewer' : `Show all ${runs.length} runs`}
            </button>
          </div>
        )}
      </div>

      {/* Error companies */}
      {errCompanies.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 10px', color: 'var(--error)' }}>
            Companies with Errors
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {errCompanies.map((c) => (
              <div key={c.id} style={{
                background: 'var(--danger-light)', border: '1px solid var(--danger-border)',
                borderRadius: 8, padding: '7px 12px', fontSize: 13,
              }}>
                <span style={{ fontWeight: 600, color: 'var(--text)' }}>{c.name}</span>
                <span style={{ color: 'var(--error)', marginLeft: 8, fontSize: 12 }}>
                  {c.scrape_error_count} error{c.scrape_error_count !== 1 ? 's' : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All auto-connected companies (httpx cloud + curl_cffi/browser runners) */}
      <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 10px', color: 'var(--text)' }}>
        Auto-Connected Companies ({companies.filter(c => c.auto_connected ?? c.enabled).length})
      </h3>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
        gap: 6,
      }}>
        {companies.filter(c => c.auto_connected ?? c.enabled).map((c) => {
          const scraped = !!c.last_scraped_at
          return (
            <div key={c.id} style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '8px 12px',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 500, fontSize: 13, color: 'var(--text)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.name}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {c.ats_platform}{c.engine ? ` · ${c.engine}` : ''}
                </div>
              </div>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: scraped ? (c.scrape_error_count > 0 ? 'var(--error)' : 'var(--success)') : 'var(--text-faint)',
                flexShrink: 0,
              }} title={scraped ? (c.scrape_error_count > 0 ? 'Has errors' : 'OK') : 'Not yet scraped'} />
            </div>
          )
        })}
      </div>
    </div>
  )
}

const td: React.CSSProperties = { padding: '8px 12px', color: 'var(--text)' }
