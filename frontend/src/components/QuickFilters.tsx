import type { Filters, Job } from '../lib/types'
import { matchesFilters, matchesLevel, matchesRemote } from '../lib/query'
import { Icon, type IconName } from './Icon'

/**
 * One-tap filters for the axes that decide whether a posting is worth opening.
 *
 * All of these already existed in the sidebar, buried as sections three and five of
 * nine — so reaching "show me remote new-grad roles" meant opening the panel and
 * scrolling past Company Tier and Role Category. These are the two questions a
 * candidate asks first, so they belong in front of the results.
 *
 * Each chip carries its live count, computed over the rows that pass every OTHER
 * active filter. That matters: a chip reading 0 tells you not to bother, and a count
 * that moves as you narrow tells you the filters are actually composing.
 */

interface Props {
  /** Count per chip key, from quickFilterCounts(). */
  counts: Record<string, number>
  filters: Filters
  onChange: (patch: Partial<Filters>) => void
}

type Chip = {
  key: string
  label: string
  icon: IconName
  color: string
  active: (f: Filters) => boolean
  patch: (on: boolean) => Partial<Filters>
  /** Applied to the already-filtered rows to produce the count. */
  test: (j: Job) => boolean
}

const CHIPS: Chip[] = [
  {
    key: 'entry',
    label: 'New grad / entry',
    icon: 'sparkles',
    color: 'var(--success)',
    // The strict shorthand: a genuinely junior experience_level, not merely
    // "no seniority word in the title".
    active: (f) => (f.level_filter || '') === 'entry',
    patch: (on) => ({ level_filter: on ? 'entry' : undefined }),
    test: (j) => matchesLevel(j, 'entry'),
  },
  {
    key: 'remote',
    label: 'Remote',
    icon: 'globe',
    color: 'var(--teal)',
    active: (f) => (f.remote || '').toLowerCase() === 'remote',
    patch: (on) => ({ remote: on ? 'Remote' : undefined }),
    test: (j) => matchesRemote(j, 'remote'),
  },
  {
    key: 'hybrid',
    label: 'Hybrid',
    icon: 'building',
    color: 'var(--primary)',
    active: (f) => (f.remote || '').toLowerCase() === 'hybrid',
    patch: (on) => ({ remote: on ? 'Hybrid' : undefined }),
    test: (j) => matchesRemote(j, 'hybrid'),
  },
  {
    key: 'h1b',
    label: 'Sponsors H1B',
    icon: 'shield',
    color: 'var(--accent-gold)',
    active: (f) => Boolean(f.h1b_only),
    patch: (on) => ({ h1b_only: on || undefined }),
    test: (j) =>
      j.sponsors_h1b === true &&
      !['high', 'medium'].includes(String(j.eligibility_risk || 'low').toLowerCase()),
  },
  {
    key: 'week',
    label: 'Posted this week',
    icon: 'clock',
    color: 'var(--warning)',
    active: (f) => Number(f.posted_within_hours) === 168,
    patch: (on) => ({ posted_within_hours: on ? 168 : undefined }),
    test: (j) => {
      const raw =
        (j.posted_date && j.posted_date_known !== false ? j.posted_date : null) || j.first_seen_at
      const t = raw ? Date.parse(String(raw)) : NaN
      return !Number.isNaN(t) && t >= Date.now() - 168 * 3600_000
    },
  },
]

/** Count, for each chip, how many rows would remain if that chip were the only
 *  thing added to the current filters.
 *
 *  Computed over the WHOLE corpus with the other active filters applied — not over
 *  the current page, which holds 50 rows and would make every count read "50". The
 *  chip's own criterion is removed from the filters first, so an already-active chip
 *  still reports its true size instead of counting itself twice.
 */
export function quickFilterCounts(rows: Job[], filters: Filters): Record<string, number> {
  const out: Record<string, number> = {}
  for (const chip of CHIPS) {
    const without = { ...filters, ...chip.patch(false) }
    out[chip.key] = rows.filter((j) => matchesFilters(j, without) && chip.test(j)).length
  }
  return out
}

export function QuickFilters({ counts, filters, onChange }: Props) {
  return (
    <div
      style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginBottom: 12 }}
      role="group"
      aria-label="Quick filters"
    >
      {CHIPS.map((chip) => {
        const on = chip.active(filters)
        const count = counts[chip.key] ?? 0
        const empty = count === 0 && !on
        return (
          <button
            key={chip.key}
            onClick={() => onChange(chip.patch(!on))}
            aria-pressed={on}
            disabled={empty}
            title={empty ? `No ${chip.label.toLowerCase()} jobs match the current filters` : undefined}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              border: `1px solid ${on ? chip.color : 'var(--border)'}`,
              background: on
                ? `color-mix(in srgb, ${chip.color} 14%, var(--surface))`
                : 'var(--surface)',
              color: on ? chip.color : 'var(--text-secondary)',
              borderRadius: 999,
              padding: '6px 12px',
              fontSize: 12.5,
              fontWeight: 650,
              cursor: empty ? 'not-allowed' : 'pointer',
              opacity: empty ? 0.45 : 1,
              boxShadow: on ? 'var(--shadow-sm)' : 'none',
              transition: 'background 120ms, border-color 120ms',
            }}
          >
            <Icon name={chip.icon} size={14} color={on ? chip.color : 'var(--text-tertiary)'} />
            {chip.label}
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: on ? chip.color : 'var(--text-tertiary)',
                background: on ? 'transparent' : 'var(--surface-muted)',
                borderRadius: 999,
                padding: on ? 0 : '1px 6px',
              }}
            >
              {count}
            </span>
          </button>
        )
      })}
    </div>
  )
}
