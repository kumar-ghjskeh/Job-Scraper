import { useState } from 'react'
import type { AnalyticsSummary } from '../lib/types'
import { Icon, type IconName } from './Icon'

export type Tab = 'entry-level' | 'best' | 'all' | 'saved' | 'applied' | 'companies' | 'health'

interface Props {
  activeTab: Tab
  onTabChange: (t: Tab) => void
  analytics: AnalyticsSummary | null
  onRunScrape: () => void
  running: boolean
  search: string
  onSearch: (q: string) => void
}

const TABS: { id: Tab; label: string; badge?: (a: AnalyticsSummary) => number; icon: IconName }[] = [
  { id: 'entry-level', label: 'Entry-Level',  badge: (a) => a.entry_level_count, icon: 'star' },
  { id: 'best',        label: 'Best Matches', badge: (a) => a.high_score_count,  icon: 'target' },
  { id: 'all',         label: 'All Jobs',                                         icon: 'list' },
  { id: 'saved',       label: 'Saved',        badge: (a) => a.saved_count,       icon: 'bookmark' },
  { id: 'applied',     label: 'Applied',      badge: (a) => a.applied_count,     icon: 'checkCircle' },
  { id: 'companies',   label: 'Companies',                                        icon: 'building' },
  { id: 'health',      label: 'Scrape Health',                                    icon: 'activity' },
]

export function TopNav({ activeTab, onTabChange, analytics, onRunScrape, running, search, onSearch }: Props) {
  const [q, setQ] = useState(search)

  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 200, background: '#FFFFFF', borderBottom: '1px solid var(--border)' }}>
      {/* Brand + search + actions */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 18,
        padding: '10px 24px', maxWidth: 1640, margin: '0 auto',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 11, flexShrink: 0 }}>
          <div style={{
            width: 38, height: 38, borderRadius: 9,
            background: 'linear-gradient(135deg, #0A66C2 0%, #004182 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 6px rgba(10,102,194,0.3)',
          }}>
            <Icon name="cpu" size={21} color="#fff" strokeWidth={2.2} />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 17, color: 'var(--text)', lineHeight: 1.1, letterSpacing: '-0.02em' }}>
              Job Scraper
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase', marginTop: 1 }}>
              RTL &amp; Design Verification Jobs
            </div>
          </div>
        </div>

        {/* Search */}
        <form
          onSubmit={(e) => { e.preventDefault(); onSearch(q.trim()) }}
          style={{ flex: 1, maxWidth: 520, position: 'relative' }}
        >
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)', display: 'flex' }}>
            <Icon name="search" size={16} />
          </span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search jobs, companies, skills…"
            style={{
              width: '100%', height: 38, paddingLeft: 36, paddingRight: q ? 64 : 14,
              background: 'var(--surface-sunken)', border: '1px solid var(--border)',
              borderRadius: 999, fontSize: 13.5, color: 'var(--text)', outline: 'none',
              transition: 'background 0.14s, border-color 0.14s',
            }}
            onFocus={(e) => { e.currentTarget.style.background = '#fff'; e.currentTarget.style.borderColor = 'var(--primary)' }}
            onBlur={(e) => { e.currentTarget.style.background = 'var(--surface-sunken)'; e.currentTarget.style.borderColor = 'var(--border)' }}
          />
          {q && (
            <button
              type="button"
              onClick={() => { setQ(''); onSearch('') }}
              style={{
                position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                background: 'var(--surface-hover)', border: 'none', borderRadius: '50%',
                width: 22, height: 22, cursor: 'pointer', display: 'flex',
                alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)',
              }}
            >
              <Icon name="x" size={13} />
            </button>
          )}
        </form>

        <div style={{ flex: 1 }} />

        {/* Run Scrape */}
        <button onClick={onRunScrape} disabled={running} className="btn btn-primary">
          {running ? (
            <><span className="spin"><Icon name="refresh" size={15} color="#fff" /></span> Scraping…</>
          ) : (
            <><Icon name="play" size={14} color="#fff" /> Run Scrape</>
          )}
        </button>
      </div>

      {/* Tabs */}
      <div style={{ borderTop: '1px solid var(--border-light)' }}>
        <div style={{
          display: 'flex', alignItems: 'center', padding: '0 24px',
          overflowX: 'auto', gap: 4, maxWidth: 1640, margin: '0 auto',
        }}>
          {TABS.map((t) => {
            const badge = analytics && t.badge ? t.badge(analytics) : null
            const active = activeTab === t.id
            return (
              <button
                key={t.id}
                onClick={() => onTabChange(t.id)}
                style={{
                  background: 'none', border: 'none',
                  borderBottom: active ? '2.5px solid var(--primary)' : '2.5px solid transparent',
                  color: active ? 'var(--primary)' : 'var(--text-muted)',
                  padding: '11px 12px', cursor: 'pointer', fontSize: 13,
                  fontWeight: active ? 700 : 500, whiteSpace: 'nowrap',
                  display: 'flex', alignItems: 'center', gap: 7,
                  transition: 'color 0.12s, border-color 0.12s', marginBottom: -1,
                }}
                onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = 'var(--text)' }}
                onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = 'var(--text-muted)' }}
              >
                <Icon name={t.icon} size={16} color={active ? 'var(--primary)' : 'currentColor'} />
                {t.label}
                {badge !== null && badge > 0 && (
                  <span style={{
                    background: active ? 'var(--primary)' : 'var(--surface-sunken)',
                    color: active ? '#fff' : 'var(--text-muted)',
                    borderRadius: 999, padding: '1px 7px', fontSize: 11, fontWeight: 700,
                    lineHeight: '16px', border: active ? 'none' : '1px solid var(--border)',
                  }}>
                    {badge > 999 ? '999+' : badge}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>
    </header>
  )
}
