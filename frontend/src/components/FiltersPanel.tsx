import type { Filters } from '../lib/types'

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
}

const PRIORITIES = ['S', 'A', 'B', 'C']
const CATEGORIES = [
  'Design Verification', 'RTL Design', 'SoC Verification',
  'CPU/GPU Verification', 'FPGA RTL', 'Formal Verification',
  'Emulation', 'Pre-Silicon Validation', 'Post-Silicon Validation',
  'EDA / Verification Tools', 'Adjacent / Backup',
]
const EXP_LEVELS = ['New Grad', 'Entry Level', '0-3 Years', 'Mid-Level', 'Senior']
const KEYWORDS = [
  'UVM', 'SystemVerilog', 'SVA', 'RTL', 'ASIC', 'SoC', 'GPU', 'CPU',
  'FPGA', 'PCIe', 'CXL', 'AXI', 'formal', 'coverage',
]

export function FiltersPanel({ filters, onChange }: Props) {
  const set = (k: keyof Filters, v: unknown) =>
    onChange({ ...filters, [k]: v || undefined })

  return (
    <div style={{
      background: '#161b22', border: '1px solid #21262d', borderRadius: 8,
      padding: 16, width: 220, flexShrink: 0,
    }}>
      <div style={{ color: '#8b949e', fontSize: 11, fontWeight: 700, marginBottom: 12, letterSpacing: '0.08em' }}>
        FILTERS
      </div>

      <Field label="Keyword search">
        <input
          placeholder="title, keywords..."
          value={filters.keyword || ''}
          onChange={(e) => set('keyword', e.target.value)}
          style={inputStyle}
        />
      </Field>

      <Field label="Status">
        <select
          value={filters.status || ''}
          onChange={(e) => set('status', e.target.value)}
          style={inputStyle}
        >
          <option value="">Active</option>
          <option value="saved">Saved</option>
          <option value="applied">Applied</option>
          <option value="ignored">Ignored</option>
          <option value="possibly_removed">Maybe removed</option>
          <option value="removed">Removed</option>
        </select>
      </Field>

      <Field label="Priority">
        <select
          value={filters.priority || ''}
          onChange={(e) => set('priority', e.target.value)}
          style={inputStyle}
        >
          <option value="">All</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}-Tier</option>)}
        </select>
      </Field>

      <Field label="Role category">
        <select
          value={filters.role_category || ''}
          onChange={(e) => set('role_category', e.target.value)}
          style={inputStyle}
        >
          <option value="">All</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </Field>

      <Field label="Experience">
        <select
          value={filters.experience_level || ''}
          onChange={(e) => set('experience_level', e.target.value)}
          style={inputStyle}
        >
          <option value="">All</option>
          {EXP_LEVELS.map((e) => <option key={e} value={e}>{e}</option>)}
        </select>
      </Field>

      <Field label="Remote status">
        <select
          value={filters.remote || ''}
          onChange={(e) => set('remote', e.target.value)}
          style={inputStyle}
        >
          <option value="">All</option>
          <option value="Remote">Remote</option>
          <option value="Hybrid">Hybrid</option>
          <option value="Onsite">Onsite</option>
        </select>
      </Field>

      <Field label="Min score">
        <input
          type="number"
          min={0}
          max={100}
          placeholder="0"
          value={filters.min_score ?? ''}
          onChange={(e) => set('min_score', e.target.value ? Number(e.target.value) : undefined)}
          style={inputStyle}
        />
      </Field>

      <Field label="New in last N hours">
        <input
          type="number"
          placeholder="e.g. 24"
          value={filters.new_since_hours ?? ''}
          onChange={(e) => set('new_since_hours', e.target.value ? Number(e.target.value) : undefined)}
          style={inputStyle}
        />
      </Field>

      <div style={{ marginTop: 12 }}>
        <div style={{ color: '#8b949e', fontSize: 11, marginBottom: 8 }}>QUICK KEYWORDS</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {KEYWORDS.map((kw) => (
            <button
              key={kw}
              onClick={() => set('keyword', filters.keyword === kw ? '' : kw)}
              style={{
                background: filters.keyword === kw ? '#1f6feb' : '#21262d',
                border: '1px solid ' + (filters.keyword === kw ? '#388bfd' : '#30363d'),
                borderRadius: 4, padding: '2px 7px', fontSize: 11,
                color: filters.keyword === kw ? '#fff' : '#8b949e',
                cursor: 'pointer',
              }}
            >
              {kw}
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={() => onChange({})}
        style={{
          marginTop: 16, width: '100%', background: 'none',
          border: '1px solid #30363d', borderRadius: 6, padding: '6px',
          color: '#8b949e', fontSize: 12, cursor: 'pointer',
        }}
      >
        Clear filters
      </button>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ color: '#8b949e', fontSize: 11, marginBottom: 4 }}>{label}</div>
      {children}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', background: '#0d1117', border: '1px solid #30363d',
  borderRadius: 6, padding: '5px 8px', color: '#e6edf3', fontSize: 12,
  outline: 'none',
}
