import { useState } from 'react'
import { api } from '../lib/api'
import type { Job } from '../lib/types'
import { PriorityBadge } from './PriorityBadge'
import { ScoreBar } from './ScoreBar'

interface Props {
  job: Job
  onClose: () => void
  onUpdate: () => void
}

export function JobModal({ job, onClose, onUpdate }: Props) {
  const [notes, setNotes] = useState(job.notes)
  const [appStatus, setAppStatus] = useState(job.application_status)
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await api.updateJobStatus(job.id, {
        active_status: job.active_status,
        application_status: appStatus,
        notes,
      })
      onUpdate()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  async function handleSetStatus(status: string) {
    await api.updateJobStatus(job.id, { active_status: status })
    onUpdate()
    onClose()
  }

  const fmt = (d: string | null) =>
    d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: 16,
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: '#161b22', border: '1px solid #30363d', borderRadius: 12,
        width: '100%', maxWidth: 680, maxHeight: '90vh', overflow: 'auto',
        padding: 28,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <h2 style={{ margin: '0 0 6px', fontSize: 18, color: '#e6edf3' }}>{job.job_title}</h2>
            <div style={{ color: '#8b949e', fontSize: 13 }}>
              {job.company} &middot; <PriorityBadge priority={job.company_priority} /> &middot; {job.location}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', fontSize: 20, padding: 0 }}
          >×</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
          {[
            ['Category', job.role_category],
            ['Experience', job.experience_level],
            ['Remote', job.remote_status],
            ['ATS', job.ats_platform],
            ['First Seen', fmt(job.first_seen_at)],
            ['Last Seen', fmt(job.last_seen_at)],
          ].map(([k, v]) => (
            <div key={k} style={{ background: '#0d1117', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ color: '#8b949e', fontSize: 11, marginBottom: 2 }}>{k}</div>
              <div style={{ color: '#e6edf3', fontSize: 13 }}>{v || '—'}</div>
            </div>
          ))}
        </div>

        <div style={{ marginBottom: 16 }}>
          <div style={{ color: '#8b949e', fontSize: 11, marginBottom: 6 }}>MATCH SCORE</div>
          <ScoreBar score={job.match_score} />
          {job.matched_keywords && (
            <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {job.matched_keywords.split(',').map((k) => (
                <span key={k} style={{
                  background: '#1f6feb33', border: '1px solid #1f6feb66',
                  borderRadius: 4, padding: '1px 6px', fontSize: 11, color: '#79c0ff',
                }}>
                  {k.trim()}
                </span>
              ))}
            </div>
          )}
        </div>

        {job.description_snippet && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ color: '#8b949e', fontSize: 11, marginBottom: 6 }}>DESCRIPTION</div>
            <div style={{
              background: '#0d1117', borderRadius: 6, padding: 12,
              color: '#c9d1d9', fontSize: 13, lineHeight: 1.6, maxHeight: 200, overflow: 'auto',
            }}>
              {job.description_snippet}
            </div>
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <div style={{ color: '#8b949e', fontSize: 11, marginBottom: 6 }}>APPLICATION STATUS</div>
          <input
            value={appStatus}
            onChange={(e) => setAppStatus(e.target.value)}
            placeholder="e.g. Applied, Phone screen, OA..."
            style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: 20 }}>
          <div style={{ color: '#8b949e', fontSize: 11, marginBottom: 6 }}>NOTES</div>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Personal notes..."
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
          />
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <a
            href={job.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              background: '#238636', color: '#fff', border: 'none', borderRadius: 6,
              padding: '7px 16px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              textDecoration: 'none', display: 'inline-block',
            }}
          >
            Apply Now
          </a>
          <button
            onClick={() => handleSetStatus('saved')}
            style={actionBtn('#bc8cff')}
          >Save</button>
          <button
            onClick={() => handleSetStatus('applied')}
            style={actionBtn('#58a6ff')}
          >Mark Applied</button>
          <button
            onClick={() => handleSetStatus('ignored')}
            style={actionBtn('#484f58')}
          >Ignore</button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              marginLeft: 'auto', background: '#1f6feb', color: '#fff',
              border: 'none', borderRadius: 6, padding: '7px 16px', fontSize: 13,
              fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? 'Saving...' : 'Save Notes'}
          </button>
        </div>
      </div>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', background: '#0d1117', border: '1px solid #30363d',
  borderRadius: 6, padding: '7px 10px', color: '#e6edf3', fontSize: 13,
  outline: 'none',
}

const actionBtn = (color: string): React.CSSProperties => ({
  background: `${color}22`, color, border: `1px solid ${color}44`,
  borderRadius: 6, padding: '7px 14px', fontSize: 13, fontWeight: 600,
  cursor: 'pointer',
})
