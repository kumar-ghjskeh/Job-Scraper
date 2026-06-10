import type { Job } from '../lib/types'
import { Icon } from './Icon'

interface Props {
  job: Job
  selected: boolean
  onClick: () => void
  onQuickAction: (action: 'saved' | 'applied' | 'ignored') => void
  extraLocations?: string[]
}

function scoreColor(s: number) {
  if (s >= 85) return 'var(--accent-gold)'
  if (s >= 75) return 'var(--primary)'
  if (s >= 65) return 'var(--teal)'
  if (s >= 50) return 'var(--warning)'
  return 'var(--text-tertiary)'
}
function scoreLabel(s: number) {
  if (s >= 85) return 'Excellent'
  if (s >= 75) return 'Strong'
  if (s >= 65) return 'Good'
  if (s >= 50) return 'Fair'
  return 'Low'
}
function expPill(level: string): string {
  switch (level) {
    case 'New Grad': return 'pill-success'
    case 'Entry Level': return 'pill-teal'
    case '0-3 Years': return 'pill-primary'
    case 'Candidate Friendly': return 'pill-teal'
    case 'Senior': return 'pill-danger'
    default: return 'pill-neutral'
  }
}
function remotePill(r: string): string {
  if (r === 'Remote') return 'pill-success'
  if (r === 'Hybrid') return 'pill-warning'
  return 'pill-neutral'
}
const isNew = (d: string) => Date.now() - new Date(d).getTime() < 24 * 60 * 60 * 1000

export function JobCard({ job, selected, onClick, onQuickAction, extraLocations = [] }: Props) {
  const fresh = isNew(job.first_seen_at)
  const sc = scoreColor(job.match_score)
  const saved = job.active_status === 'saved'
  const risk = job.eligibility_risk
  const h1b = job.sponsors_h1b

  const keywords = job.matched_keywords
    ? job.matched_keywords.split(',').map((k) => k.trim()).filter(Boolean).slice(0, 6)
    : []
  const snippet = job.cleaned_description || job.description_snippet || ''

  return (
    <div className={`job-card${selected ? ' selected' : ''}`} onClick={onClick}>
      {/* Top row */}
      <div style={{ display: 'flex', gap: 13, alignItems: 'flex-start' }}>
        <div style={{
          width: 46, height: 46, borderRadius: 10, background: 'var(--primary-light)',
          border: '1px solid var(--primary-mid)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', fontSize: 18, fontWeight: 800, color: 'var(--primary)',
          flexShrink: 0, letterSpacing: '-0.02em',
        }}>
          {job.company.charAt(0).toUpperCase()}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 7 }}>
            <div style={{ fontSize: 14.5, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.35, flex: 1, minWidth: 0 }}>
              {job.job_title}
            </div>
            {fresh && <span className="pill pill-primary" style={{ fontWeight: 800, letterSpacing: '0.05em', fontSize: 10 }}>NEW</span>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 4, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>{job.company}</span>
            <span className={`badge tier-${(job.company_priority || 'c').toLowerCase()}`}>{job.company_priority}</span>
            {job.ats_platform && <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>via {job.ats_platform}</span>}
          </div>
        </div>

        {/* Score ring */}
        <div style={{
          width: 52, height: 52, borderRadius: '50%', background: 'var(--surface-muted)',
          border: `2.5px solid ${sc}`, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <div style={{ fontSize: 16, fontWeight: 800, color: sc, lineHeight: 1 }}>{job.match_score}</div>
          <div style={{ fontSize: 8, color: sc, fontWeight: 700, letterSpacing: '0.02em', marginTop: 1 }}>{scoreLabel(job.match_score)}</div>
        </div>
      </div>

      {/* Meta badges */}
      <div style={{ display: 'flex', gap: 7, marginTop: 11, flexWrap: 'wrap', alignItems: 'center' }}>
        {job.location && (
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Icon name="mapPin" size={13} color="var(--text-tertiary)" /> {job.location}
            {extraLocations.length > 0 && (
              <span style={{ color: 'var(--primary)', fontWeight: 600 }}>&nbsp;+{extraLocations.length} {extraLocations.length === 1 ? 'location' : 'locations'}</span>
            )}
          </span>
        )}
        {job.remote_status && job.remote_status !== 'Unknown' && (
          <span className={`pill ${remotePill(job.remote_status)}`}>{job.remote_status}</span>
        )}
        {job.experience_level && job.experience_level !== 'Unknown' && (
          <span className={`pill ${expPill(job.experience_level)}`}>{job.experience_level}</span>
        )}
        {job.role_category && job.role_category !== 'Unknown' && (
          <span className="pill pill-neutral">{job.role_category}</span>
        )}
        {risk === 'high' && <span className="pill pill-danger"><Icon name="shield" size={11} /> Citizenship/Clearance</span>}
        {risk === 'medium' && <span className="pill pill-warning"><Icon name="shield" size={11} /> Eligibility — review</span>}
        {h1b === true && <span className="pill pill-teal"><Icon name="passport" size={11} /> Sponsors H1B</span>}
        {h1b === false && <span className="pill pill-warning"><Icon name="passport" size={11} /> No H1B sponsorship</span>}
      </div>

      {keywords.length > 0 && (
        <div style={{ display: 'flex', gap: 5, marginTop: 10, flexWrap: 'wrap' }}>
          {keywords.map((kw) => <span key={kw} className="skill-chip">{kw}</span>)}
        </div>
      )}

      {snippet && (
        <div style={{
          marginTop: 10, fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55,
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>{snippet}</div>
      )}

      {/* Bottom */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginTop: 12, paddingTop: 11, borderTop: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
          {saved && <span style={{ fontSize: 11.5, color: 'var(--primary)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 3 }}><Icon name="bookmarkFilled" size={12} color="var(--primary)" /> Saved</span>}
          {job.active_status === 'applied' && <span style={{ fontSize: 11.5, color: 'var(--success)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 3 }}><Icon name="checkCircle" size={12} color="var(--success)" /> Applied</span>}
          {job.active_status === 'ignored' && <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>Ignored</span>}
          <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>
            {fresh ? 'first seen ' : ''}{new Date(job.first_seen_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 7 }}>
          <button
            onClick={(e) => { e.stopPropagation(); onQuickAction('saved') }}
            title={saved ? 'Unsave' : 'Save job'}
            style={{
              background: saved ? 'var(--primary-light)' : 'var(--surface-muted)',
              border: `1px solid ${saved ? 'var(--primary-mid)' : 'var(--border)'}`,
              borderRadius: 7, padding: '6px 9px', cursor: 'pointer', display: 'flex', alignItems: 'center',
            }}
          >
            <Icon name={saved ? 'bookmarkFilled' : 'bookmark'} size={15} color={saved ? 'var(--primary)' : 'var(--text-secondary)'} />
          </button>
          <a
            href={job.safe_apply_url || job.apply_url}
            target="_blank" rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="btn btn-primary"
            style={{ padding: '6px 14px', fontSize: 12.5 }}
          >
            Apply <Icon name="external" size={13} color="var(--on-primary)" />
          </a>
        </div>
      </div>
    </div>
  )
}
