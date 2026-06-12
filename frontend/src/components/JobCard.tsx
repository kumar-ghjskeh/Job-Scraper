import type { Job } from '../lib/types'
import { Icon } from './Icon'
import { matchColor } from './ScoreGauge'
import { CompanyLogo } from './CompanyLogo'
import { fmtDate } from '../lib/datetime'

interface Props {
  job: Job
  selected: boolean
  onClick: () => void
  onQuickAction: (action: 'saved' | 'applied' | 'ignored') => void
  extraLocations?: string[]
  resumeMatch?: number
  /** On the Resume Matches tab, show the resume-match % as the primary ring. */
  resumePrimary?: boolean
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
    case 'Entry Level': case 'Junior': return 'pill-teal'
    case 'Associate': case '0-3 Years': case 'Candidate Friendly': return 'pill-primary'
    case 'Mid-Level': return 'pill-neutral'
    case 'Senior': case 'Staff': case 'Principal': case 'Lead': case 'Manager': return 'pill-danger'
    default: return 'pill-neutral'
  }
}
function locationPill(label: string): string {
  if (label === 'Remote - USA') return 'pill-success'
  if (label === 'Hybrid') return 'pill-warning'
  if (label === 'Multi-location USA') return 'pill-primary'
  return 'pill-neutral'
}
const isNew = (d: string) => Date.now() - new Date(d).getTime() < 24 * 60 * 60 * 1000

export function JobCard({ job, selected, onClick, onQuickAction, extraLocations = [], resumeMatch, resumePrimary }: Props) {
  const fresh = isNew(job.first_seen_at)
  const sc = scoreColor(job.match_score)
  const saved = job.active_status === 'saved'
  const rm = resumeMatch ?? job.resume_match
  // On the Resume tab the ring shows the resume match; elsewhere the relevance score.
  const showResumeRing = !!resumePrimary && rm !== undefined && rm !== null
  const risk = job.eligibility_risk
  const h1b = job.sponsors_h1b

  // Drop scoring artifacts (USA is the default, priority/recency aren't skills) so
  // the chips read as real skills/protocols only.
  const NOISE_KW = /^(usa|us|united states|priority-[a-d]|recent|fresh|new)$/i
  const keywords = job.matched_keywords
    ? job.matched_keywords.split(',').map((k) => k.trim()).filter((k) => k && !NOISE_KW.test(k)).slice(0, 6)
    : []
  const snippet = job.cleaned_description || job.description_snippet || ''

  return (
    <div className={`job-card${selected ? ' selected' : ''}`} onClick={onClick}>
      {/* Top row */}
      <div style={{ display: 'flex', gap: 13, alignItems: 'flex-start' }}>
        <CompanyLogo company={job.company} size={46} radius={10} />

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
            {!showResumeRing && rm !== undefined && rm !== null && (
              <span className="pill" style={{ background: 'transparent', color: matchColor(rm), border: `1px solid ${matchColor(rm)}`, fontWeight: 700, fontSize: 10.5 }}>
                <Icon name="target" size={10} color={matchColor(rm)} /> Resume {rm}%
              </span>
            )}
            {job.ats_platform && <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>via {job.ats_platform}</span>}
          </div>
        </div>

        {/* Score ring — resume match on the Resume tab, else relevance score */}
        {(() => {
          const ringColor = showResumeRing ? matchColor(rm!) : sc
          return (
            <div style={{
              width: 52, height: 52, borderRadius: '50%', background: 'var(--surface-muted)',
              border: `2.5px solid ${ringColor}`, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              <div style={{ fontSize: 16, fontWeight: 800, color: ringColor, lineHeight: 1 }}>
                {showResumeRing ? `${rm}%` : job.match_score}
              </div>
              <div style={{ fontSize: 8, color: ringColor, fontWeight: 700, letterSpacing: '0.02em', marginTop: 1 }}>
                {showResumeRing ? 'MATCH' : scoreLabel(job.match_score)}
              </div>
            </div>
          )
        })()}
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
        {job.location_label && job.location_label !== 'Location Unknown' ? (
          <span className={`pill ${locationPill(job.location_label)}`}>{job.location_label}</span>
        ) : job.remote_status && job.remote_status !== 'Unknown' ? (
          <span className={`pill ${locationPill(job.remote_status)}`}>{job.remote_status}</span>
        ) : null}
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
            {job.posted_date ? `Posted ${fmtDate(job.posted_date)}` : 'Recently posted'}
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
