import { useState } from 'react'
import type { Job } from '../lib/types'
import { JobModal } from './JobModal'
import { PriorityBadge } from './PriorityBadge'
import { ScoreBar } from './ScoreBar'
import { StatusBadge } from './StatusBadge'

interface Props {
  jobs: Job[]
  onUpdate: () => void
  loading?: boolean
  showRemoved?: boolean
}

const fmt = (d: string | null) =>
  d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—'

const isNew = (d: string) => {
  const diff = Date.now() - new Date(d).getTime()
  return diff < 24 * 60 * 60 * 1000
}

export function JobTable({ jobs, onUpdate, loading }: Props) {
  const [selected, setSelected] = useState<Job | null>(null)
  const [sort, setSort] = useState<{ col: string; dir: 'asc' | 'desc' }>({
    col: 'match_score', dir: 'desc',
  })

  const sorted = [...jobs].sort((a, b) => {
    const av = (a as unknown as Record<string, unknown>)[sort.col]
    const bv = (b as unknown as Record<string, unknown>)[sort.col]
    if (av === undefined || bv === undefined) return 0
    if (typeof av === 'string' && typeof bv === 'string') {
      return sort.dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    }
    if (typeof av === 'number' && typeof bv === 'number') {
      return sort.dir === 'asc' ? av - bv : bv - av
    }
    return 0
  })

  const toggleSort = (col: string) => {
    setSort((s) => s.col === col ? { col, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { col, dir: 'desc' })
  }

  const SortArrow = ({ col }: { col: string }) => (
    <span style={{ color: '#484f58', fontSize: 10, marginLeft: 3 }}>
      {sort.col === col ? (sort.dir === 'asc' ? '▲' : '▼') : '⇅'}
    </span>
  )

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: '#8b949e' }}>
        Loading jobs...
      </div>
    )
  }

  if (!jobs.length) {
    return (
      <div style={{
        padding: 40, textAlign: 'center', color: '#8b949e',
        background: '#161b22', borderRadius: 8, border: '1px solid #21262d',
      }}>
        No jobs found. Try adjusting filters or run a scrape.
      </div>
    )
  }

  return (
    <>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #21262d' }}>
              {[
                { key: 'job_title',    label: 'Title' },
                { key: 'company',      label: 'Company' },
                { key: 'company_priority', label: 'Tier' },
                { key: 'location',     label: 'Location' },
                { key: 'experience_level', label: 'Level' },
                { key: 'match_score',  label: 'Score' },
                { key: 'first_seen_at', label: 'First seen' },
                { key: 'active_status', label: 'Status' },
                { key: '_actions',     label: 'Actions' },
              ].map(({ key, label }) => (
                <th
                  key={key}
                  onClick={() => key !== '_actions' && toggleSort(key)}
                  style={{
                    padding: '8px 10px', textAlign: 'left', color: '#8b949e',
                    fontWeight: 600, fontSize: 11, letterSpacing: '0.05em',
                    cursor: key !== '_actions' ? 'pointer' : 'default',
                    userSelect: 'none', whiteSpace: 'nowrap',
                    background: '#0d1117',
                  }}
                >
                  {label}
                  {key !== '_actions' && <SortArrow col={key} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((job) => {
              const fresh = isNew(job.first_seen_at)
              return (
                <tr
                  key={job.id}
                  style={{
                    borderBottom: '1px solid #21262d',
                    background: fresh ? 'rgba(31,111,235,0.04)' : 'transparent',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#161b22')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = fresh ? 'rgba(31,111,235,0.04)' : 'transparent')}
                >
                  <td style={td} onClick={() => setSelected(job)}>
                    <span style={{ color: '#e6edf3', fontWeight: 500 }}>{job.job_title}</span>
                    {fresh && (
                      <span style={{
                        marginLeft: 6, background: '#1f6feb44', color: '#79c0ff',
                        fontSize: 10, padding: '1px 5px', borderRadius: 3, fontWeight: 700,
                      }}>NEW</span>
                    )}
                  </td>
                  <td style={td} onClick={() => setSelected(job)}>
                    <span style={{ color: '#c9d1d9' }}>{job.company}</span>
                  </td>
                  <td style={td} onClick={() => setSelected(job)}>
                    <PriorityBadge priority={job.company_priority} />
                  </td>
                  <td style={{ ...td, color: '#8b949e', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                    onClick={() => setSelected(job)}>
                    {job.location || '—'}
                  </td>
                  <td style={{ ...td, color: '#8b949e' }} onClick={() => setSelected(job)}>
                    {job.experience_level}
                  </td>
                  <td style={td} onClick={() => setSelected(job)}>
                    <ScoreBar score={job.match_score} />
                  </td>
                  <td style={{ ...td, color: '#8b949e', whiteSpace: 'nowrap' }} onClick={() => setSelected(job)}>
                    {fmt(job.first_seen_at)}
                  </td>
                  <td style={td} onClick={() => setSelected(job)}>
                    <StatusBadge status={job.active_status} />
                  </td>
                  <td style={{ ...td, whiteSpace: 'nowrap' }}>
                    <a
                      href={job.apply_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'inline-block', background: '#238636',
                        color: '#fff', borderRadius: 4, padding: '3px 9px',
                        fontSize: 12, fontWeight: 600, textDecoration: 'none',
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      Apply
                    </a>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {selected && (
        <JobModal
          job={selected}
          onClose={() => setSelected(null)}
          onUpdate={onUpdate}
        />
      )}
    </>
  )
}

const td: React.CSSProperties = {
  padding: '9px 10px',
  verticalAlign: 'middle',
}
