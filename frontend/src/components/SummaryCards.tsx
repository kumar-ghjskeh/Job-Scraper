import type { AnalyticsSummary } from '../lib/types'
import { Icon, type IconName } from './Icon'

interface Props {
  analytics: AnalyticsSummary | null
}

function Card({ label, value, sub, color, icon }: {
  label: string; value: number | string; sub?: string; color: string; icon: IconName
}) {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', padding: '14px 16px',
      display: 'flex', alignItems: 'center', gap: 13,
      flex: '1 1 150px', minWidth: 0, boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: 9, background: `${color}16`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Icon name={icon} size={20} color={color} strokeWidth={2.1} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 23, fontWeight: 700, color: 'var(--text)', lineHeight: 1.05, letterSpacing: '-0.02em' }}>
          {value}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, marginTop: 2 }}>{label}</div>
        {sub && <div style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 1 }}>{sub}</div>}
      </div>
    </div>
  )
}

export function SummaryCards({ analytics }: Props) {
  if (!analytics) {
    return (
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 70, flex: '1 1 150px', borderRadius: 8 }} />
        ))}
      </div>
    )
  }

  const lastRun = analytics.last_run
  const lastRunStr = lastRun?.started_at
    ? new Date(lastRun.started_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Never'

  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
      <Card label="Active Jobs"  value={analytics.total_active}       color="#057642" icon="briefcase" sub="Live postings" />
      <Card label="New Today"    value={analytics.new_24h}            color="#0A66C2" icon="sparkles" sub={analytics.new_24h > 0 ? 'Fresh postings' : 'No new postings'} />
      <Card label="Entry-Level"  value={analytics.entry_level_count}  color="#0E7490" icon="graduation" sub="New grad / 0–3 yrs" />
      <Card label="USA Jobs"     value={analytics.usa_count}          color="#1B4965" icon="globe" />
      <Card label="Remote"       value={analytics.remote_count}       color="#0E7490" icon="home" />
      <Card label="Score ≥ 70"   value={analytics.high_score_count}   color="#915907" icon="star" sub="Strong + Excellent" />
      <Card label="Saved"        value={analytics.saved_count}        color="#0A66C2" icon="bookmark" />
      <Card label="Applied"      value={analytics.applied_count}      color="#057642" icon="checkCircle" sub={lastRun ? `Last run ${lastRunStr}` : undefined} />
    </div>
  )
}
