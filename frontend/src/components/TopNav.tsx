import { useState } from 'react'
import type { AnalyticsSummary } from '../lib/types'
import type { Theme } from '../lib/theme'
import { Icon, type IconName } from './Icon'

export type Tab = 'all' | 'resume' | 'entry-level' | 'best' | 'saved' | 'applied' | 'companies' | 'health'

interface Props {
  activeTab: Tab
  onTabChange: (t: Tab) => void
  analytics: AnalyticsSummary | null
  onRefresh: () => void
  refreshing: boolean
  search: string
  onSearch: (q: string) => void
  theme: Theme
  onToggleTheme: () => void
}

const TABS: { id: Tab; label: string; badge?: (a: AnalyticsSummary) => number; icon: IconName }[] = [
  { id: 'all',         label: 'All Jobs',       icon: 'list' },
  { id: 'resume',      label: 'Resume Matches', icon: 'target' },
  { id: 'entry-level', label: 'New Grad',       badge: (a) => a.entry_level_count, icon: 'graduation' },
  { id: 'saved',       label: 'Saved',          badge: (a) => a.saved_count,       icon: 'bookmark' },
  { id: 'applied',     label: 'Applied',        badge: (a) => a.applied_count,     icon: 'checkCircle' },
  { id: 'companies',   label: 'Companies',      icon: 'building' },
  { id: 'health',      label: 'Data Health',    icon: 'activity' },
]

export function TopNav({
  activeTab, onTabChange, analytics, onRefresh, refreshing, search, onSearch, theme, onToggleTheme,
}: Props) {
  const [q, setQ] = useState(search)

  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 200, background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
      {/* Brand + search + actions */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 18,
        padding: '10px 24px', maxWidth: 1640, margin: '0 auto',
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 11, flexShrink: 0 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10, background: 'var(--brand-tile)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
            border: '1px solid rgba(255,255,255,0.06)', flexShrink: 0,
          }}>
            <img src="/ashborne-logo.png" alt="Ashborne Silicon"
              style={{ width: 34, height: 34, objectFit: 'contain' }} />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16.5, color: 'var(--text-primary)', lineHeight: 1.1, letterSpacing: '-0.02em' }}>
              Ashborne Silicon
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--text-secondary)', letterSpacing: '0.04em', marginTop: 1 }}>
              USA RTL · DV · ASIC · SoC · FPGA · DFT jobs
            </div>
          </div>
        </div>

        {/* Search */}
        <form
          onSubmit={(e) => { e.preventDefault(); onSearch(q.trim()) }}
          style={{ flex: 1, maxWidth: 540, position: 'relative' }}
        >
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)', display: 'flex' }}>
            <Icon name="search" size={16} />
          </span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by title, company, skill, protocol, or state…"
            style={{
              width: '100%', height: 38, paddingLeft: 36, paddingRight: q ? 64 : 14,
              background: 'var(--surface-muted)', border: '1px solid var(--border)',
              borderRadius: 999, fontSize: 13.5, color: 'var(--text-primary)', outline: 'none',
              transition: 'background 0.14s, border-color 0.14s',
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--primary)' }}
            onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
          />
          {q && (
            <button type="button" onClick={() => { setQ(''); onSearch('') }}
              style={{
                position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '50%',
                width: 22, height: 22, cursor: 'pointer', display: 'flex',
                alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)',
              }}>
              <Icon name="x" size={13} />
            </button>
          )}
        </form>

        <div style={{ flex: 1 }} />

        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          aria-label="Toggle theme"
          style={{
            width: 38, height: 38, borderRadius: 10, cursor: 'pointer',
            background: 'var(--surface-muted)', border: '1px solid var(--border)',
            color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'background 0.14s, color 0.14s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)' }}
        >
          <Icon name={theme === 'light' ? 'moon' : 'sun'} size={18} />
        </button>

        {/* Refresh */}
        <button onClick={onRefresh} disabled={refreshing} className="btn btn-primary">
          {refreshing ? (
            <><span className="spin"><Icon name="refresh" size={15} color="var(--on-primary)" /></span> Updating…</>
          ) : (
            <><Icon name="refresh" size={15} color="var(--on-primary)" /> Refresh Jobs</>
          )}
        </button>
      </div>

      {/* Tabs */}
      <div style={{ borderTop: '1px solid var(--border)' }}>
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
                  color: active ? 'var(--primary)' : 'var(--text-secondary)',
                  padding: '11px 12px', cursor: 'pointer', fontSize: 13,
                  fontWeight: active ? 700 : 500, whiteSpace: 'nowrap',
                  display: 'flex', alignItems: 'center', gap: 7,
                  transition: 'color 0.12s, border-color 0.12s', marginBottom: -1,
                }}
                onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = 'var(--text-primary)' }}
                onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = 'var(--text-secondary)' }}
              >
                <Icon name={t.icon} size={16} color={active ? 'var(--primary)' : 'currentColor'} />
                {t.label}
                {badge !== null && badge > 0 && (
                  <span style={{
                    background: active ? 'var(--primary)' : 'var(--surface-muted)',
                    color: active ? 'var(--on-primary)' : 'var(--text-secondary)',
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
