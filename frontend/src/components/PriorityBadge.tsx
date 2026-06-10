interface Props { priority: string }

const colors: Record<string, string> = {
  S: '#ffd700',
  A: '#58a6ff',
  B: '#3fb950',
  C: '#8b949e',
}

export function PriorityBadge({ priority }: Props) {
  const color = colors[priority] || '#8b949e'
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 7px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 700,
      color,
      background: `${color}22`,
      border: `1px solid ${color}44`,
      letterSpacing: '0.05em',
    }}>
      {priority}
    </span>
  )
}
