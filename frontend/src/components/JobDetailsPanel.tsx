import { useState } from 'react'
import { api } from '../lib/api'
import type { Job } from '../lib/types'
import { Icon } from './Icon'

interface Props {
  job: Job | null
  onClose: () => void
  onUpdate: () => void
}

type DetailTab = 'overview' | 'score' | 'description' | 'source' | 'notes'

function scoreColor(score: number): string {
  if (score >= 85) return '#057642'
  if (score >= 75) return '#0A66C2'
  if (score >= 65) return '#0E7490'
  if (score >= 50) return '#915907'
  return '#6B7280'
}

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      background: 'var(--bg)', borderRadius: 8, padding: '10px 12px',
    }}>
      <span style={{
        fontSize: 11, color: 'var(--text-muted)', fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 3,
      }}>
        {label}
      </span>
      <span style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500, wordBreak: 'break-all' }}>
        {value || '—'}
      </span>
    </div>
  )
}

function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const pct = Math.min(100, (score / max) * 100)
  const color = scoreColor(score)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`, height: '100%', background: color,
          borderRadius: 3, transition: 'width 0.4s ease',
        }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, color, minWidth: 28, textAlign: 'right' }}>
        {score}
      </span>
    </div>
  )
}

const fmt = (d: string | null) =>
  d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'

export function JobDetailsPanel({ job, onClose, onUpdate }: Props) {
  const [detailTab, setDetailTab] = useState<DetailTab>('overview')
  const [notes, setNotes] = useState('')
  const [appStatus, setAppStatus] = useState('')
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  const [lastJobId, setLastJobId] = useState<number | null>(null)
  if (job && job.id !== lastJobId) {
    setLastJobId(job.id)
    setNotes(job.notes || '')
    setAppStatus(job.application_status || '')
    setDetailTab('overview')
  }

  if (!job) return null

  const sc = scoreColor(job.match_score)

  async function handleSetStatus(status: string) {
    await api.updateJobStatus(job!.id, { active_status: status })
    onUpdate()
  }

  async function handleSaveNotes() {
    setSaving(true)
    try {
      await api.updateJobStatus(job!.id, { application_status: appStatus, notes })
      onUpdate()
    } finally {
      setSaving(false)
    }
  }

  function handleCopyTitle() {
    navigator.clipboard.writeText(job!.job_title).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  let scoreBreakdown: Record<string, number> = {}
  try {
    if (job.score_breakdown_json) scoreBreakdown = JSON.parse(job.score_breakdown_json)
  } catch { /* ignore */ }

  const keywords = job.matched_keywords
    ? job.matched_keywords.split(',').map((k) => k.trim()).filter(Boolean)
    : []

  const DETAIL_TABS: { id: DetailTab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'score', label: 'Score' },
    { id: 'description', label: 'Description' },
    { id: 'source', label: 'Source' },
    { id: 'notes', label: 'Notes' },
  ]

  return (
    <aside style={{
      width: 'var(--panel-width)', flexShrink: 0,
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      display: 'flex', flexDirection: 'column',
      position: 'sticky', top: 'calc(var(--nav-height) + 8px)',
      maxHeight: 'calc(100vh - var(--nav-height) - 24px)',
      overflow: 'hidden',
      alignSelf: 'flex-start',
      boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
    }}>
      {/* Panel header */}
      <div style={{
        padding: '16px 20px 12px',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0, marginRight: 8 }}>
            <h3 style={{
              margin: '0 0 4px', fontSize: 15, fontWeight: 700,
              color: 'var(--text)', lineHeight: 1.3, wordBreak: 'break-word',
            }}>
              {job.job_title}
            </h3>
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              {job.company} · {job.location || 'Location TBD'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
            <button
              onClick={handleCopyTitle}
              title="Copy job title"
              style={{
                background: copied ? 'var(--success-light)' : 'var(--surface-sunken)',
                border: '1px solid var(--border)', borderRadius: 6,
                padding: '5px 9px', fontSize: 11, cursor: 'pointer', fontWeight: 600,
                color: copied ? 'var(--success)' : 'var(--text-muted)',
                whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', gap: 4,
              }}
            >
              <Icon name={copied ? 'check' : 'copy'} size={12} /> {copied ? 'Copied' : 'Copy'}
            </button>
            <button
              onClick={onClose}
              title="Close"
              style={{
                background: 'var(--surface-sunken)', border: '1px solid var(--border)',
                borderRadius: 6, width: 28, height: 28, cursor: 'pointer', color: 'var(--text-muted)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            ><Icon name="x" size={15} /></button>
          </div>
        </div>

        {/* Score badge row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          <div style={{
            background: `${sc}15`, border: `1px solid ${sc}30`,
            borderRadius: 6, padding: '3px 10px',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{ fontSize: 18, fontWeight: 700, color: sc }}>{job.match_score}</span>
            <span style={{ fontSize: 12, color: sc, fontWeight: 600 }}>
              {job.relevance_score_label || 'Relevance Score'}
            </span>
          </div>
          {job.is_entry_level && (
            <span style={{
              background: '#DCFCE7', color: '#16A34A',
              fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 4,
            }}>
              Entry-Level
            </span>
          )}
          {job.is_candidate_friendly && !job.is_entry_level && (
            <span style={{
              background: '#CFFAFE', color: '#0891B2',
              fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 4,
            }}>
              Candidate Friendly
            </span>
          )}
          {job.is_remote_usa && (
            <span style={{
              background: 'var(--teal-light)', color: 'var(--teal)',
              fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 4,
            }}>
              Remote USA
            </span>
          )}
          {job.eligibility_risk === 'high' && (
            <span className="pill pill-danger"><Icon name="shield" size={11} /> Citizenship/Clearance</span>
          )}
          {job.eligibility_risk === 'medium' && (
            <span className="pill pill-warning"><Icon name="shield" size={11} /> Eligibility — review</span>
          )}
          {job.sponsors_h1b === true && (
            <span className="pill pill-teal"><Icon name="passport" size={11} /> Sponsors H1B</span>
          )}
          {job.sponsors_h1b === false && (
            <span className="pill pill-warning"><Icon name="passport" size={11} /> No H1B sponsorship</span>
          )}
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
          <a
            href={job.safe_apply_url || job.apply_url}
            target="_blank" rel="noopener noreferrer"
            className="btn btn-primary"
          >
            Apply Now <Icon name="external" size={14} color="#fff" />
          </a>
          <button
            onClick={() => handleSetStatus(job.active_status === 'saved' ? 'active' : 'saved')}
            className="btn"
            style={{
              background: job.active_status === 'saved' ? 'var(--primary-light)' : 'var(--surface-sunken)',
              border: `1px solid ${job.active_status === 'saved' ? 'var(--primary-mid)' : 'var(--border)'}`,
              color: job.active_status === 'saved' ? 'var(--primary)' : 'var(--text-muted)',
            }}
          >
            <Icon name={job.active_status === 'saved' ? 'bookmarkFilled' : 'bookmark'} size={14} />
            {job.active_status === 'saved' ? 'Saved' : 'Save'}
          </button>
          <button
            onClick={() => handleSetStatus(job.active_status === 'applied' ? 'active' : 'applied')}
            className="btn"
            style={{
              background: job.active_status === 'applied' ? 'var(--success-light)' : 'var(--surface-sunken)',
              border: `1px solid ${job.active_status === 'applied' ? 'var(--success-border)' : 'var(--border)'}`,
              color: job.active_status === 'applied' ? 'var(--success)' : 'var(--text-muted)',
            }}
          >
            <Icon name="checkCircle" size={14} /> Applied
          </button>
          <button
            onClick={() => handleSetStatus('ignored')}
            className="btn btn-ghost"
            style={{ borderColor: 'var(--border)' }}
          >
            <Icon name="eyeOff" size={14} /> Ignore
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', borderBottom: '1px solid var(--border)',
        padding: '0 16px', flexShrink: 0, gap: 2,
        overflowX: 'auto',
      }}>
        {DETAIL_TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setDetailTab(id)}
            style={{
              background: 'none', border: 'none',
              borderBottom: detailTab === id ? '2px solid var(--primary)' : '2px solid transparent',
              color: detailTab === id ? 'var(--primary)' : 'var(--text-muted)',
              padding: '8px 10px', cursor: 'pointer', fontSize: 12,
              fontWeight: detailTab === id ? 600 : 400,
              whiteSpace: 'nowrap',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>

        {detailTab === 'overview' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <MetaRow label="Company" value={job.company} />
            <MetaRow label="Priority" value={`${job.company_priority}-Tier`} />
            <MetaRow label="Role Category" value={job.role_category} />
            <MetaRow label="Experience" value={job.experience_level} />
            <MetaRow label="Work Mode" value={job.location_label || job.remote_status} />
            <MetaRow label="ATS Platform" value={job.ats_platform} />
            <MetaRow label="Source Reliability" value={job.source_reliability} />
            <MetaRow label="Seniority Confidence" value={job.seniority_confidence ? `${job.seniority_confidence}%` : '—'} />
            <MetaRow label="Classification Conf." value={job.classification_confidence ? `${job.classification_confidence}%` : '—'} />
            <MetaRow label="Data Quality" value={job.data_quality_score ? `${job.data_quality_score}%` : '—'} />
            <MetaRow label="Country" value={job.country || (job.is_usa ? 'USA' : '—')} />
            <MetaRow label="State" value={job.state} />
            {job.years_required_min !== null && (
              <MetaRow label="Years Required" value={
                job.years_required_max
                  ? `${job.years_required_min}–${job.years_required_max} yrs`
                  : `${job.years_required_min}+ yrs`
              } />
            )}
            <MetaRow label="Company Category" value={job.company_category} />
            <MetaRow label="First Seen" value={fmt(job.first_seen_at)} />
            <MetaRow label="Last Seen" value={fmt(job.last_seen_at)} />
            <MetaRow
              label="Posted Date"
              value={job.posted_date_known && job.posted_date
                ? fmt(job.posted_date)
                : 'Unknown — using first-seen'}
            />
            {job.saved_at && (
              <MetaRow label="Saved On" value={fmt(job.saved_at)} />
            )}
            {job.applied_at && (
              <MetaRow label="Applied On" value={fmt(job.applied_at)} />
            )}
          </div>
        )}

        {detailTab === 'score' && (
          <div>
            {/* Score explanation */}
            <div style={{
              background: 'var(--primary-light)',
              border: '1px solid #BFDBFE',
              borderRadius: 8, padding: '10px 14px', marginBottom: 16,
              fontSize: 12, color: '#1E40AF', lineHeight: 1.6,
            }}>
              <strong>Job Relevance Score</strong> — Based on RTL/DV job relevance, title
              keywords, skills, company priority, seniority, USA location, and posting
              recency. It is not resume-based yet.
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{
                fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6,
              }}>
                Job Relevance Score
              </div>
              <ScoreBar score={job.match_score} />
            </div>

            {keywords.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{
                  fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                  textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8,
                }}>
                  Matched Keywords
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                  {keywords.map((kw) => (
                    <span key={kw} style={{
                      background: 'var(--primary-light)', color: 'var(--primary)',
                      fontSize: 12, padding: '3px 9px', borderRadius: 5, fontWeight: 500,
                    }}>
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {Object.keys(scoreBreakdown).length > 0 ? (
              <div>
                <div style={{
                  fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                  textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8,
                }}>
                  Score Breakdown
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {Object.entries(scoreBreakdown).map(([reason, pts]) => (
                    <div key={reason} style={{
                      display: 'flex', justifyContent: 'space-between',
                      alignItems: 'center', padding: '7px 12px',
                      background: (pts as number) > 0 ? '#F0FDF4' : '#FEF2F2',
                      border: `1px solid ${(pts as number) > 0 ? '#BBF7D0' : '#FECACA'}`,
                      borderRadius: 6,
                    }}>
                      <span style={{ fontSize: 12, color: 'var(--text)', flex: 1 }}>{reason}</span>
                      <span style={{
                        fontSize: 13, fontWeight: 700,
                        color: (pts as number) > 0 ? 'var(--success)' : 'var(--error)',
                        marginLeft: 8,
                      }}>
                        {(pts as number) > 0 ? `+${pts}` : pts}
                      </span>
                    </div>
                  ))}
                </div>
                {/* Total */}
                <div style={{
                  display: 'flex', justifyContent: 'space-between',
                  padding: '8px 12px', marginTop: 8,
                  background: `${scoreColor(job.match_score)}15`,
                  border: `1px solid ${scoreColor(job.match_score)}30`,
                  borderRadius: 6,
                }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
                    Final Score (capped 0–100)
                  </span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: scoreColor(job.match_score) }}>
                    {job.match_score}
                  </span>
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', padding: '16px 0' }}>
                Score breakdown not available for this job.
              </div>
            )}
          </div>
        )}

        {detailTab === 'description' && (
          <div>
            {job.relevance_reason && (
              <div style={{
                background: 'var(--primary-light)', border: '1px solid var(--primary-mid)',
                borderRadius: 8, padding: '8px 12px', marginBottom: 14,
                fontSize: 12, color: '#1E40AF', lineHeight: 1.6,
              }}>
                <strong>Why this job:</strong> {job.relevance_reason}
              </div>
            )}
            {(job.cleaned_description || job.full_description_text || job.description_snippet) ? (
              <div style={{
                fontSize: 13, color: 'var(--text)', lineHeight: 1.75,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {job.cleaned_description || job.full_description_text || job.description_snippet}
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', paddingTop: 20 }}>
                No description available.
              </div>
            )}
          </div>
        )}

        {detailTab === 'source' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <MetaRow label="Job ID (Internal)" value={String(job.id)} />
            <MetaRow label="Company Job ID" value={job.job_id_from_company} />
            <MetaRow label="ATS Platform" value={job.ats_platform} />
            <div style={{ gridColumn: '1 / -1' }}>
              <MetaRow label="Apply URL Status" value={
                <span>
                  <span style={{
                    color: job.apply_url_status === 'ok' ? 'var(--success)' : 'var(--warning)',
                    fontWeight: 600,
                  }}>
                    {job.apply_url_status || '—'}
                  </span>
                  {job.apply_url_reason && (
                    <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>
                      — {job.apply_url_reason}
                    </span>
                  )}
                </span>
              } />
            </div>
            <div>
              <div style={{
                fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4,
              }}>
                Safe Apply URL
              </div>
              <a
                href={job.safe_apply_url || job.apply_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: 11, color: 'var(--primary)', wordBreak: 'break-all',
                  display: 'block', lineHeight: 1.5,
                }}
              >
                {job.safe_apply_url || job.apply_url || '—'}
              </a>
            </div>
            {job.original_apply_url && job.original_apply_url !== job.safe_apply_url && (
              <div>
                <div style={{
                  fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                  textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4,
                }}>
                  Original Apply URL
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-faint)', wordBreak: 'break-all', lineHeight: 1.5 }}>
                  {job.original_apply_url}
                </span>
              </div>
            )}
            {job.source_url && (
              <div>
                <div style={{
                  fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                  textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4,
                }}>
                  Source URL
                </div>
                <a
                  href={job.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: 11, color: 'var(--primary)', wordBreak: 'break-all' }}
                >
                  {job.source_url}
                </a>
              </div>
            )}
            <MetaRow label="First Seen" value={fmt(job.first_seen_at)} />
            <MetaRow label="Last Seen" value={fmt(job.last_seen_at)} />
            <MetaRow label="Location Confidence" value={
              job.location_confidence > 0 ? `${Math.round(job.location_confidence * 100)}%` : '—'
            } />
          </div>
        )}

        {detailTab === 'notes' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{
                fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                textTransform: 'uppercase', letterSpacing: '0.04em',
                display: 'block', marginBottom: 6,
              }}>
                Application Status
              </label>
              <input
                value={appStatus}
                onChange={(e) => setAppStatus(e.target.value)}
                placeholder="e.g. Applied, Phone screen, OA, Offer..."
                style={{
                  width: '100%', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '8px 12px', fontSize: 13,
                  background: 'var(--surface)', color: 'var(--text)', outline: 'none',
                }}
              />
            </div>

            <div>
              <label style={{
                fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                textTransform: 'uppercase', letterSpacing: '0.04em',
                display: 'block', marginBottom: 6,
              }}>
                Personal Notes
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={5}
                placeholder="Add notes about this job, follow-ups, contacts..."
                style={{
                  width: '100%', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '8px 12px', fontSize: 13,
                  background: 'var(--surface)', color: 'var(--text)',
                  outline: 'none', resize: 'vertical', fontFamily: 'inherit',
                }}
              />
            </div>

            <button
              onClick={handleSaveNotes}
              disabled={saving}
              style={{
                background: 'var(--primary)', color: '#fff',
                border: 'none', borderRadius: 8, padding: '9px 20px',
                fontSize: 13, fontWeight: 600,
                cursor: saving ? 'not-allowed' : 'pointer',
                opacity: saving ? 0.7 : 1, alignSelf: 'flex-start',
              }}
            >
              {saving ? 'Saving...' : 'Save Notes'}
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}
