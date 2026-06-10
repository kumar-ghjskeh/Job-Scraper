interface Props { status: string }

const cfg: Record<string, { label: string; color: string }> = {
  active:            { label: 'Active',    color: '#3fb950' },
  possibly_removed:  { label: 'Maybe off', color: '#d29922' },
  removed:           { label: 'Removed',   color: '#f85149' },
  applied:           { label: 'Applied',   color: '#58a6ff' },
  saved:             { label: 'Saved',     color: '#bc8cff' },
  ignored:           { label: 'Ignored',   color: '#484f58' },
}

export function StatusBadge({ status }: Props) {
  const { label, color } = cfg[status] ?? { label: status, color: '#8b949e' }
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 7px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 600,
      color,
      background: `${color}22`,
      border: `1px solid ${color}44`,
    }}>
      {label}
    </span>
  )
}
