import type { Job } from '../lib/types'
import { Icon } from './Icon'

interface Props {
  job: Job
  selected: boolean
  onClick: () => void
  onQuickAction: (action: 'saved' | 'applied' | 'ignored') => void
}

function scoreColor(s: number) {
  if (s >= 85) return '#057642'
  if (s >= 75) return '#0A66C2'
  if (s >= 65) return '#0E7490'
  if (s >= 50) return '#915907'
  return '#6B7280'
}
function scoreLabel(s: number) {
  if (s >= 85) return 'Excellent'
  if (s >= 75) return 'Strong'
  if (s >= 65) return 'Good'
  if (s >= 50) return 'Fair'
  return 'Low'
}
function expBadge(level: string) {
  switch (level) {
    case 'New Grad':            return { bg: '#E6F4EA', color: '#057642', border: '#B7E0C4' }
    case 'Entry Level':         return { bg: '#E0F5F9', color: '#0E7490', border: '#BAE6EF' }
    case '0-3 Years':           return { bg: '#EAF1FB', color: '#0A66C2', border: '#C7E0F9' }
    case 'Candidate Friendly':  return { bg: '#E0F5F9', color: '#0E7490', border: '#BAE6EF' }
    case 'Mid-Level':           return { bg: '#F0EFEC', color: '#57534E', border: '#E2E0DC' }
    case 'Senior':              return { bg: '#FBE9E9', color: '#B91C1C', border: '#F3C5C5' }
    default:                    return { bg: '#F7F6F3', color: '#78716C', border: '#E2E0DC' }
  }
}
const isNew = (d: string) => Date.now() - new Date(d).getTime() < 24 * 60 * 60 * 1000

export function JobCard({ job, selected, onClick, onQuickAction }: Props) {
  const fresh = isNew(job.first_seen_at)
  const sc = scoreColor(job.match_score)
  const exp = expBadge(job.experience_level)
  const saved = job.active_status === 'saved'

  const keywords = job.matched_keywords
    ? job.matched_keywords.split(',').map((k) => k.trim()).filter(Boolean).slice(0, 6)
    : []
  const snippet = job.cleaned_description || job.description_snippet || ''

  return (
    <div className={`job-card${selected ? ' selected' : ''}`} onClick={onClick}>
      {/* Top row */}
      <div style={{ display: 'flex', gap: 13, alignItems: 'flex-start' }}>
        <div style={{
          width: 46, height: 46, borderRadius: 10,
          background: 'linear-gradient(135deg, #EAF1FB, #D6E6F7)',
          border: '1px solid var(--primary-mid)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 18, fontWeight: 800, color: 'var(--primary)', flexShrink: 0, letterSpacing: '-0.02em',
        }}>
          {job.company.charAt(0).toUpperCase()}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 7 }}>
            <div style={{ fontSize: 14.5, fontWeight: 700, color: 'var(--text)', lineHeight: 1.35, flex: 1, minWidth: 0 }}>
              {job.job_title}
            </div>
            {fresh && (
              <span style={{
                background: '#EAF1FB', color: '#0A66C2', border: '1px solid #C7E0F9',
                fontSize: 10, fontWeight: 800, padding: '2px 7px', borderRadius: 4,
                flexShrink: 0, letterSpacing: '0.05em',
              }}>NEW</span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 4, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: 'var(--text)', fontWeight: 600 }}>{job.company}</span>
            <span className={`badge tier-${(job.company_priority || 'c').toLowerCase()}`}>{job.company_priority}</span>
            {job.ats_platform && (
              <span style={{ fontSize: 11.5, color: 'var(--text-faint)' }}>via {job.ats_platform}</span>
            )}
          </div>
        </div>

        {/* Score ring */}
        <div style={{
          width: 52, height: 52, borderRadius: '50%', background: `${sc}10`,
          border: `2.5px solid ${sc}`, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <div style={{ fontSize: 16, fontWeight: 800, color: sc, lineHeight: 1 }}>{job.match_score}</div>
          <div style={{ fontSize: 8, color: sc, fontWeight: 700, letterSpacing: '0.02em', marginTop: 1 }}>
            {scoreLabel(job.match_score)}
          </div>
        </div>
      </div>

      {/* Meta badges */}
      <div style={{ display: 'flex', gap: 7, marginTop: 11, flexWrap: 'wrap', alignItems: 'center' }}>
        {job.location && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Icon name="mapPin" size={13} color="var(--text-faint)" /> {job.location}
          </span>
        )}
        {job.remote_status && job.remote_status !== 'Unknown' && (
          <span style={{
            fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999,
            background: job.remote_status === 'Remote' ? '#E6F4EA' : job.remote_status === 'Hybrid' ? '#FBF1DC' : '#F0EFEC',
            color: job.remote_status === 'Remote' ? '#057642' : job.remote_status === 'Hybrid' ? '#915907' : '#57534E',
            border: `1px solid ${job.remote_status === 'Remote' ? '#B7E0C4' : job.remote_status === 'Hybrid' ? '#F2D9A6' : '#E2E0DC'}`,
          }}>{job.remote_status}</span>
        )}
        {job.experience_level && job.experience_level !== 'Unknown' && (
          <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999, background: exp.bg, color: exp.color, border: `1px solid ${exp.border}` }}>
            {job.experience_level}
          </span>
        )}
        {job.role_category && job.role_category !== 'Unknown' && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--surface-sunken)', padding: '2px 8px', borderRadius: 999, border: '1px solid var(--border)' }}>
            {job.role_category}
          </span>
        )}
      </div>

      {keywords.length > 0 && (
        <div style={{ display: 'flex', gap: 5, marginTop: 10, flexWrap: 'wrap' }}>
          {keywords.map((kw) => <span key={kw} className="skill-chip">{kw}</span>)}
        </div>
      )}

      {snippet && (
        <div style={{
          marginTop: 10, fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.55,
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>{snippet}</div>
      )}

      {/* Bottom */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginTop: 12, paddingTop: 11, borderTop: '1px solid var(--border-light)',
      }}>
        <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
          {saved && <span style={{ fontSize: 11.5, color: 'var(--primary)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 3 }}><Icon name="bookmarkFilled" size={12} color="var(--primary)" /> Saved</span>}
          {job.active_status === 'applied' && <span style={{ fontSize: 11.5, color: 'var(--success)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 3 }}><Icon name="checkCircle" size={12} color="var(--success)" /> Applied</span>}
          {job.active_status === 'ignored' && <span style={{ fontSize: 11.5, color: 'var(--text-faint)', fontWeight: 600 }}>Ignored</span>}
          <span style={{ fontSize: 11.5, color: 'var(--text-faint)' }}>
            {new Date(job.first_seen_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 7 }}>
          <button
            onClick={(e) => { e.stopPropagation(); onQuickAction('saved') }}
            title={saved ? 'Unsave' : 'Save job'}
            style={{
              background: saved ? 'var(--primary-light)' : 'var(--surface-sunken)',
              border: `1px solid ${saved ? 'var(--primary-mid)' : 'var(--border)'}`,
              borderRadius: 7, padding: '6px 9px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', transition: 'all 0.12s',
            }}
          >
            <Icon name={saved ? 'bookmarkFilled' : 'bookmark'} size={15} color={saved ? 'var(--primary)' : 'var(--text-muted)'} />
          </button>
          <a
            href={job.safe_apply_url || job.apply_url}
            target="_blank" rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="btn btn-primary"
            style={{ padding: '6px 14px', fontSize: 12.5 }}
          >
            Apply <Icon name="external" size={13} color="#fff" />
          </a>
        </div>
      </div>
    </div>
  )
}
