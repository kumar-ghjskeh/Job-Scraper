import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Filters, JobFacets } from '../lib/types'

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
  totalCount: number
}

const CATEGORIES = [
  'Design Verification', 'RTL Design', 'SoC Verification',
  'CPU/GPU Verification', 'FPGA RTL', 'Formal Verification',
  'Emulation', 'Pre-Silicon Validation', 'Post-Silicon Validation',
  'EDA / Verification Tools', 'Adjacent / Backup',
]
const QUICK_KWS = [
  'UVM', 'SystemVerilog', 'SVA', 'Verilog', 'VHDL',
  'ASIC', 'SoC', 'FPGA', 'formal', 'coverage',
  'PCIe', 'AXI', 'CXL', 'CPU', 'GPU',
]
const US_STATES = ['CA', 'TX', 'WA', 'MA', 'NY', 'AZ', 'OR', 'CO', 'GA', 'IL', 'PA', 'VA', 'NC', 'MN']

const inp: React.CSSProperties = {
  width: '100%', background: 'var(--surface)',
  border: '1px solid var(--border)', borderRadius: 7,
  padding: '7px 10px', color: 'var(--text)', fontSize: 13,
  outline: 'none', transition: 'border-color 0.15s',
}

function SectionHead({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 800, color: 'var(--text-muted)',
      letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8,
    }}>
      {title}
    </div>
  )
}

function Toggle({ on, onToggle, label, sub }: { on: boolean; onToggle: () => void; label: string; sub?: string }) {
  return (
    <label style={{
      display: 'flex', alignItems: 'center', gap: 10,
      cursor: 'pointer', userSelect: 'none', marginBottom: 12,
    }}>
      <div
        className="toggle-track"
        onClick={onToggle}
        style={{ background: on ? 'var(--primary)' : 'var(--border-strong)' }}
      >
        <div className="toggle-thumb" style={{ left: on ? 19 : 3 }} />
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{sub}</div>}
      </div>
    </label>
  )
}

export function FilterSidebar({ filters, onChange, totalCount }: Props) {
  const [facets, setFacets] = useState<JobFacets | null>(null)

  useEffect(() => {
    api.getFacets(filters.usa_only !== false, filters.include_software)
      .then(setFacets)
      .catch(() => {/* non-fatal */})
  }, [filters.usa_only, filters.include_software])

  const set = (k: keyof Filters, v: unknown) =>
    onChange({ ...filters, [k]: v === '' ? undefined : v })

  const hasFilters = Object.entries(filters).some(([k, v]) => {
    if (k === 'usa_only' && v === true) return false
    if (k === 'include_senior' && v === false) return false
    return v !== undefined && v !== '' && v !== false
  })

  return (
    <aside style={{
      width: 'var(--sidebar-width)', flexShrink: 0,
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      position: 'sticky', top: 'calc(var(--nav-height) + 8px)',
      maxHeight: 'calc(100vh - var(--nav-height) - 24px)',
      overflowY: 'auto', alignSelf: 'flex-start',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '14px 16px 10px',
        borderBottom: '1px solid var(--border)',
        position: 'sticky', top: 0, background: 'var(--surface)', zIndex: 1,
      }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>Filters</span>
          {facets && (
            <span style={{ fontSize: 12, color: 'var(--text-faint)', marginLeft: 8 }}>
              {totalCount.toLocaleString()} jobs
            </span>
          )}
        </div>
        {hasFilters && (
          <button
            onClick={() => onChange({ usa_only: true, include_senior: false })}
            style={{
              background: 'none', border: 'none', color: 'var(--primary)',
              fontSize: 12, fontWeight: 700, cursor: 'pointer', padding: 0,
            }}
          >
            Clear all
          </button>
        )}
      </div>

      <div style={{ padding: '12px 16px' }}>

        {/* Search */}
        <div style={{ marginBottom: 16 }}>
          <SectionHead title="Search" />
          <input
            placeholder="Title, company, keyword…"
            value={filters.keyword || ''}
            onChange={(e) => set('keyword', e.target.value)}
            style={inp}
            onFocus={(e) => (e.target.style.borderColor = 'var(--primary)')}
            onBlur={(e) => (e.target.style.borderColor = 'var(--border)')}
          />
        </div>

        {/* Toggles — USA-only is the default platform behavior; software roles
            are excluded by design, so only the seniority toggle remains. */}
        <div style={{ marginBottom: 14 }}>
          <Toggle
            on={!!filters.include_senior}
            onToggle={() => set('include_senior', !filters.include_senior)}
            label="Show Senior Roles"
            sub="Include Sr / Staff / Principal / Lead"
          />
        </div>

        {/* Company Tier */}
        <div style={{ marginBottom: 16 }}>
          <SectionHead title="Company Tier" />
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {[
              { v: 'S', label: 'S — Dream', cls: 'tier-s' },
              { v: 'A', label: 'A — Target', cls: 'tier-a' },
              { v: 'B', label: 'B — Good', cls: 'tier-b' },
              { v: 'C', label: 'C — Backup', cls: 'tier-c' },
            ].map(({ v, label, cls }) => (
              <button
                key={v}
                onClick={() => set('priority', filters.priority === v ? '' : v)}
                className={filters.priority === v ? cls : ''}
                title={label}
                style={{
                  border: filters.priority === v ? '1.5px solid currentColor' : '1px solid var(--border)',
                  background: filters.priority === v ? undefined : 'var(--bg)',
                  borderRadius: 6, padding: '4px 10px',
                  fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  color: filters.priority === v ? undefined : 'var(--text-muted)',
                }}
              >
                {v}
              </button>
            ))}
          </div>
        </div>

        {/* Role Category */}
        <div style={{ marginBottom: 16 }}>
          <SectionHead title="Role Category" />
          <select
            value={filters.role_category || ''}
            onChange={(e) => set('role_category', e.target.value)}
            style={inp}
          >
            <option value="">All categories</option>
            {CATEGORIES.map((c) => {
              const f = facets?.role_categories.find((r) => r.value === c)
              return (
                <option key={c} value={c}>
                  {c}{f ? ` (${f.count})` : ''}
                </option>
              )
            })}
          </select>
        </div>

        {/* Remote Status */}
        <div style={{ marginBottom: 16 }}>
          <SectionHead title="Remote Status" />
          <div style={{ display: 'flex', gap: 5 }}>
            {['Remote', 'Hybrid', 'Onsite'].map((v) => {
              const active = filters.remote === v
              return (
                <button
                  key={v}
                  onClick={() => set('remote', active ? '' : v)}
                  className={active ? 'pill-primary' : ''}
                  style={{
                    flex: 1, border: active ? '1px solid var(--primary-mid)' : '1px solid var(--border)',
                    background: active ? undefined : 'var(--surface-muted)',
                    borderRadius: 6, padding: '5px 0', fontSize: 11, fontWeight: 600,
                    cursor: 'pointer', color: active ? 'var(--primary)' : 'var(--text-secondary)',
                    transition: 'all 0.1s',
                  }}
                >
                  {v}
                </button>
              )
            })}
          </div>
        </div>

        {/* Min Score */}
        <div style={{ marginBottom: 16 }}>
          <SectionHead title="Min Relevance Score" />
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {[0, 50, 65, 75, 85].map((n) => {
              const active = (filters.min_score ?? 0) === n
              return (
                <button
                  key={n}
                  onClick={() => set('min_score', active ? undefined : n === 0 ? undefined : n)}
                  style={{
                    background: active ? 'var(--primary)' : 'var(--bg)',
                    border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
                    borderRadius: 6, padding: '4px 9px',
                    fontSize: 12, fontWeight: 600, cursor: 'pointer',
                    color: active ? '#fff' : 'var(--text-muted)',
                  }}
                >
                  {n === 0 ? 'Any' : `${n}+`}
                </button>
              )
            })}
          </div>
        </div>

        {/* New Since */}
        <div style={{ marginBottom: 16 }}>
          <SectionHead title="Posted Within" />
          <select
            value={filters.new_since_hours ?? ''}
            onChange={(e) => set('new_since_hours', e.target.value ? Number(e.target.value) : undefined)}
            style={inp}
          >
            <option value="">All time</option>
            <option value="6">Last 6 hours</option>
            <option value="24">Last 24 hours</option>
            <option value="48">Last 48 hours</option>
            <option value="168">Last 7 days</option>
          </select>
        </div>

        {/* US State */}
        <div style={{ marginBottom: 16 }}>
          <SectionHead title="US State" />
          <select
            value={filters.state || ''}
            onChange={(e) => set('state', e.target.value)}
            style={inp}
          >
            <option value="">All states</option>
            {US_STATES.map((s) => {
              const f = facets?.states.find((x) => x.value === s)
              return (
                <option key={s} value={s}>
                  {s}{f ? ` (${f.count})` : ''}
                </option>
              )
            })}
          </select>
        </div>

        {/* Quick Keyword Chips */}
        <div style={{ marginBottom: 8 }}>
          <SectionHead title="Quick Keywords" />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {QUICK_KWS.map((kw) => {
              const active = filters.keyword === kw
              return (
                <button
                  key={kw}
                  onClick={() => set('keyword', active ? '' : kw)}
                  style={{
                    background: active ? 'var(--primary-light)' : 'var(--bg)',
                    border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
                    borderRadius: 5, padding: '3px 8px',
                    fontSize: 11, fontWeight: 500, cursor: 'pointer',
                    color: active ? 'var(--primary)' : 'var(--text-muted)',
                  }}
                >
                  {kw}
                </button>
              )
            })}
          </div>
        </div>

        {/* Facet counts summary */}
        {facets && (
          <div style={{
            marginTop: 16, padding: '10px 12px',
            background: 'var(--bg)', borderRadius: 8,
            border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Quick Stats
            </div>
            {[
              { label: 'True Entry-Level', value: facets.entry_level_count, color: 'var(--success)' },
              { label: 'Remote', value: facets.remote_count, color: 'var(--teal)' },
              { label: 'New Today', value: facets.new_24h_count, color: 'var(--primary)' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{
                display: 'flex', justifyContent: 'space-between',
                alignItems: 'center', marginBottom: 5,
              }}>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{label}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color }}>{value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
