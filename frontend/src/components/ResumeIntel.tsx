import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import type { ResumeProfile, SkillGap } from '../lib/types'
import { Icon } from './Icon'

interface Props {
  onChanged: () => void
}

const ACCEPT = '.pdf,.docx,.txt,.tex'

export function ResumeIntel({ onChanged }: Props) {
  const [profile, setProfile] = useState<ResumeProfile | null>(null)
  const [filename, setFilename] = useState('')
  const [gaps, setGaps] = useState<SkillGap[]>([])
  const [highMatch, setHighMatch] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [drag, setDrag] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const loadGaps = useCallback(async () => {
    try { const g = await api.getSkillGaps(); setGaps(g.gaps || []); setHighMatch(g.high_match_jobs || 0) } catch { /* */ }
  }, [])

  useEffect(() => {
    api.getResume().then((r) => {
      setProfile(r.profile)
      setFilename(r.filename || '')
      if (r.profile) loadGaps()
    }).catch(() => {})
  }, [loadGaps])

  async function handleFile(file: File) {
    setUploading(true); setError('')
    try {
      const res = await api.uploadResume(file)
      setProfile(res.profile); setFilename(res.filename)
      await loadGaps()
      onChanged()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function handleRemove() {
    await api.deleteResume()
    setProfile(null); setFilename(''); setGaps([])
    onChanged()
  }

  const maxGap = gaps.length ? gaps[0].count : 1

  return (
    <aside style={{
      width: 'var(--sidebar-width)', flexShrink: 0, background: 'var(--surface)',
      border: '1px solid var(--border)', borderRadius: 'var(--radius)',
      position: 'sticky', top: 'calc(var(--nav-height) + 8px)',
      maxHeight: 'calc(100vh - var(--nav-height) - 24px)', overflowY: 'auto', alignSelf: 'flex-start',
    }}>
      <div style={{ padding: '14px 16px' }}>
        {!profile ? (
          <>
            <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)', marginBottom: 4 }}>Resume Intelligence</div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 14, lineHeight: 1.5 }}>
              Upload your resume to rank every job by fit, see matched & missing skills, and get safe tailoring advice. It stays private on your backend.
            </div>
            <div
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) handleFile(f) }}
              style={{
                border: `2px dashed ${drag ? 'var(--primary)' : 'var(--border-strong)'}`,
                background: drag ? 'var(--primary-light)' : 'var(--surface-muted)',
                borderRadius: 10, padding: '28px 16px', textAlign: 'center', cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {uploading ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                  <span className="spin"><Icon name="refresh" size={22} color="var(--primary)" /></span>
                  <span style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>Parsing resume…</span>
                </div>
              ) : (
                <>
                  <Icon name="fileText" size={28} color="var(--primary)" />
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginTop: 8 }}>Drop your resume or click</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3 }}>PDF · DOCX · TXT · TeX</div>
                </>
              )}
            </div>
            {error && <div style={{ fontSize: 11.5, color: 'var(--danger)', marginTop: 8 }}>{error}</div>}
            <input ref={inputRef} type="file" accept={ACCEPT} style={{ display: 'none' }}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
          </>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>Your Resume</div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => inputRef.current?.click()} title="Replace"
                  style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', padding: 0 }}>Replace</button>
                <button onClick={handleRemove} title="Remove"
                  style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', padding: 0 }}>Remove</button>
              </div>
            </div>
            <input ref={inputRef} type="file" accept={ACCEPT} style={{ display: 'none' }}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />

            <div style={{ background: 'var(--surface-muted)', borderRadius: 8, padding: '10px 12px', marginBottom: 14 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)' }}>{profile.role_focus}</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginTop: 2 }}>
                {[profile.degree, profile.grad_date].filter(Boolean).join(' · ') || filename}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                {profile.all_skills.slice(0, 12).map((s) => (
                  <span key={s} className="skill-chip" style={{ fontSize: 10 }}>{s}</span>
                ))}
                {profile.all_skills.length > 12 && (
                  <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', alignSelf: 'center' }}>+{profile.all_skills.length - 12}</span>
                )}
              </div>
              {profile.projects.length > 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 8 }}>{profile.projects.length} projects detected</div>
              )}
            </div>

            <div className="section-header">Skill Gaps · top missing</div>
            {gaps.length === 0 ? (
              <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>No common gaps across your high-match jobs.</div>
            ) : (
              <>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8 }}>across {highMatch} high-match jobs</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                  {gaps.slice(0, 8).map((g) => (
                    <div key={g.skill} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11.5, color: 'var(--text-secondary)', width: 96, flexShrink: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{g.skill}</span>
                      <div style={{ flex: 1, height: 6, background: 'var(--surface-muted)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ width: `${Math.round(100 * g.count / maxGap)}%`, height: '100%', background: 'var(--warning)', borderRadius: 3 }} />
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', width: 18, textAlign: 'right' }}>{g.count}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </aside>
  )
}
