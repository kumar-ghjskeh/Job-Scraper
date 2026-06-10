interface Props { score: number }

export function ScoreBar({ score }: Props) {
  const color =
    score >= 75 ? '#3fb950' :
    score >= 50 ? '#d29922' :
    '#8b949e'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{
        width: 52, height: 6, background: '#21262d', borderRadius: 3, overflow: 'hidden'
      }}>
        <div style={{
          width: `${score}%`, height: '100%', background: color, borderRadius: 3,
          transition: 'width 0.3s'
        }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, color, minWidth: 26 }}>{score}</span>
    </div>
  )
}
