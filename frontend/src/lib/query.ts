/**
 * Client-side job querying — the exact semantics the API used to apply.
 *
 * This mirrors `_build_job_query` in backend/app/main.py. Filtering ~1,500 rows
 * in JS is instant, so moving it into the browser removes a network round trip
 * per keystroke rather than adding work. The rules below are deliberately kept
 * one-to-one with the server so results do not quietly drift:
 *
 *   - USA-only is STRICT: a posting must be positively identified as US.
 *   - The relevance gate hides Software/Compiler, Unknown and Adjacent/Backup.
 *   - Recency uses the effective date — the real posted date when the source
 *     published one, else when we first saw it — so undated sources (Google,
 *     Meta) are not invisible, and the filter agrees with the card's own label.
 *   - Search ranks title hits above body mentions, because broad domain terms
 *     ("RTL") otherwise match most of the corpus and the top result is wrong.
 *   - One card per company+role; siblings at other sites collapse into it.
 */
import type { Filters, Job } from './types'

// Hidden unless `include_adjacent` is set. 'Physical Design' is here because
// backend implementation — floorplan, place-and-route, STA, timing closure,
// signoff — is a different career track from RTL design and verification. These
// were previously filed under RTL Design and the verification categories (30 of
// them as "RTL Design", twelve as "Formal Verification"), so 11% of the visible
// US jobs were roles outside the board's scope. Still reachable, just not default.
// MUST match snapshot.HIDDEN_CATEGORIES in the backend. RTL design and design
// verification are the whole scope of this board; these are real disciplines whose
// postings are kept but not shown by default, and include_adjacent still reaches
// them. Post-Silicon Validation, DFT and EDA/Verification Tools were added once the
// title-level scope gate stopped RTL and DV roles from being misfiled into them.
const HIDDEN_CATEGORIES = new Set([
  'Software / Compiler', 'Unknown', 'Adjacent / Backup', 'Physical Design',
  'Post-Silicon Validation', 'DFT', 'EDA / Verification Tools',
])

const lc = (s: unknown) => String(s ?? '').toLowerCase()

/** Real posted date when known, else first-seen. Mirrors _effective_date(). */
export function effectiveDate(j: Job): number {
  const raw =
    (j.posted_date && j.posted_date_known !== false ? j.posted_date : null) || j.first_seen_at
  const t = raw ? Date.parse(String(raw)) : NaN
  return Number.isNaN(t) ? 0 : t
}

/** Ranks how well a row answers the query. Mirrors _keyword_rank(). */
export function keywordRank(j: Job, query: string): number {
  const q = query.trim().toLowerCase()
  if (!q) return 0
  const toks = q.split(/\s+/).filter(Boolean)
  const title = lc(j.job_title)
  const ntitle = lc(j.normalized_title)
  const company = lc(j.company)
  if (title.includes(q)) return 100
  if (ntitle.includes(q)) return 92
  if (company.includes(q)) return 88
  if (toks.length > 1 && toks.every((t) => title.includes(t))) return 75
  if (lc(j.matched_keywords).includes(q)) return 60
  if (lc(j.role_category).includes(q)) return 55
  if (toks.some((t) => title.includes(t))) return 40
  return 10
}

/** Fields a free-text query searches, mirroring the server's field list. */
function haystack(j: Job, bodies?: Record<string, string>): string {
  return [
    j.job_title,
    j.normalized_title,
    j.company,
    j.matched_keywords,
    j.role_category,
    j.experience_level,
    j.state,
    j.location,
    j.ats_platform,
    j.job_skills,
    j.description_snippet,
    bodies?.[String(j.id)] || '',
  ]
    .map(lc)
    .join(' ')
}

/** Seniority levels that count as genuinely junior, for the `entry` shorthand. */
const JUNIOR_LEVELS = new Set(['new grad', 'entry level', 'junior', 'associate'])

/** The experience_level values the sidebar offers. Must mirror SENIORITY_LEVELS in
 *  FilterSidebar.tsx — a chip whose value is not here falls through to the
 *  shorthand branches and silently filters nothing, which is the bug this
 *  function was written to fix. */
const SENIORITY_LEVEL_NAMES = new Set([
  'new grad', 'entry level', 'junior', 'associate', 'mid-level',
  'senior', 'staff', 'principal', 'lead', 'manager',
])

/** Does this posting match a seniority selection?
 *
 *  The sidebar sets `level_filter` to a comma list of experience_level values
 *  ("New Grad,Entry Level"), but this only ever compared the WHOLE string against
 *  the literals 'entry' and 'senior'. Neither matched, so both branches were
 *  skipped and the Seniority filter did nothing at all — picking "New Grad" returned
 *  the unfiltered board.
 *
 *  Both shapes are now handled: the explicit level names the sidebar sends, and the
 *  'entry' / 'senior' shorthands other callers use.
 */
export function matchesLevel(j: Job, levelFilter: string): boolean {
  const wanted = levelFilter.split(',').map((s) => lc(s).trim()).filter(Boolean)
  if (!wanted.length) return true
  const level = lc(j.experience_level)
  return wanted.some((want) => {
    // An explicit level name always wins, so the sidebar's chips behave
    // consistently: picking "Senior" means experience_level === Senior (134 jobs),
    // not the broader is_senior flag (309). Otherwise "Senior" and "Principal" —
    // adjacent chips in the same row — would have been counted different ways.
    if (SENIORITY_LEVEL_NAMES.has(want)) return level === want
    if (want === 'entry') {
      // Strict: a genuinely junior posting. is_candidate_friendly is deliberately
      // NOT enough on its own — it means "no seniority word, RTL-ish title, under
      // four years, A-tier company", which described 132 of 498 visible jobs while
      // only 32 had a junior experience_level. Treating that as "entry level"
      // sends a new grad at a pile of mid-level reqs.
      return (j.is_entry_level ?? false) || JUNIOR_LEVELS.has(level)
    }
    if (want === 'senior') return j.is_senior ?? false
    return level === want
  })
}

/** Does this posting match a remote selection?
 *
 *  Three fields describe remoteness and they disagree: remote_status said 31 of 498
 *  visible jobs were Remote, location_label said 37, and is_remote_usa said 15, with
 *  28 rows contradicting each other outright. They are each right about their own
 *  input — remote_status reads the description, is_remote_usa reads the location
 *  string — so a posting listed "Mountain View, CA or Remote" came back Hybrid and a
 *  Remote filter missed it.
 *
 *  Union rather than pick a winner: for a job seeker, failing to show a
 *  remote-eligible posting is the worse error.
 */
export function matchesRemote(j: Job, want: string): boolean {
  const w = lc(want)
  const status = lc(j.remote_status)
  const label = lc(j.location_label)
  if (w === 'remote') {
    return status.includes('remote') || label.includes('remote') || (j.is_remote_usa ?? false)
  }
  if (w === 'hybrid') {
    // Remote wins, so the three buckets partition the board and facet counts sum
    // to the total. A 'Mountain View, CA or Remote' posting is remote-eligible,
    // which is the more useful answer for someone filtering on it.
    if (matchesRemote(j, 'remote')) return false
    return status.includes('hybrid') || label.includes('hybrid')
  }
  if (w === 'onsite') {
    // Onsite means neither of the others, so a posting flagged remote by ANY signal
    // is not onsite — otherwise it shows under both.
    return !matchesRemote(j, 'remote') && !matchesRemote(j, 'hybrid')
  }
  return status.includes(w) || label.includes(w)
}

export function matchesFilters(j: Job, f: Filters, bodies?: Record<string, string>): boolean {
  // USA-only, strict. "Location unknown" is not "in the US".
  if (f.usa_only !== false && !j.is_usa) return false
  if (!f.include_software && j.is_software_only) return false
  if (!f.include_adjacent && HIDDEN_CATEGORIES.has(String(j.role_category))) return false
  if (f.include_senior === false && j.is_senior) return false

  if (f.company && lc(j.company) !== lc(f.company)) return false
  if (f.priority && String(j.company_priority) !== String(f.priority)) return false
  if (f.role_category && String(j.role_category) !== String(f.role_category)) return false
  if (f.state && lc(j.state) !== lc(f.state)) return false
  if (f.remote && !matchesRemote(j, f.remote)) return false
  if (f.min_score != null && (j.new_grad_fit ?? 0) < Number(f.min_score)) return false
  // H1B: STRICT — only employers known to sponsor, and only postings whose own
  // text does not demand citizenship, a green card or ITAR access. The old line
  // was `j.sponsors_h1b === false`, which (a) let every unknown employer through
  // and (b) read a field the corpus never carried, so it matched everything.
  if (f.h1b_only) {
    if (j.sponsors_h1b !== true) return false
    const risk = lc(j.eligibility_risk || 'low')
    if (risk === 'high' || risk === 'medium') return false
  }

  if (f.level_filter && !matchesLevel(j, f.level_filter)) return false
  if (f.posted_within_hours) {
    if (effectiveDate(j) < Date.now() - Number(f.posted_within_hours) * 3600_000) return false
  }
  if (f.new_since_hours) {
    if (Date.parse(String(j.first_seen_at)) < Date.now() - Number(f.new_since_hours) * 3600_000) {
      return false
    }
  }
  if (f.keyword && f.keyword.trim()) {
    const hay = haystack(j, bodies)
    // Every token must appear somewhere — an AND of tokens, as the server did.
    const ok = f.keyword
      .trim()
      .toLowerCase()
      .split(/\s+/)
      .every((t) => hay.includes(t))
    if (!ok) return false
  }
  if (f.skills) {
    const need = String(f.skills)
      .split(',')
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean)
    const hay = `${lc(j.job_skills)} ${lc(j.matched_keywords)} ${lc(j.description_snippet)}`
    if (!need.every((s) => hay.includes(s))) return false
  }
  return true
}

/** Recency multiplier applied to the FIT-based sorts.
 *
 *  The fit sorts ignored age entirely, so a 90-day-old posting scoring 95 outranked
 *  a two-day-old posting scoring 93 — on a board whose median visible posting is 52
 *  days old, that put the least actionable jobs on top. Measured distribution at the
 *  time: 9% of visible jobs were a week old or newer, 70% were over 30 days.
 *
 *  Bounded on purpose. It falls to 0.75 and no further, so freshness decides between
 *  comparable jobs without letting a fresh but poorly-matched posting leapfrog a
 *  strong one. Explicit sorts (posted_date, company, job_title) are left pure —
 *  someone who picked a sort gets that sort.
 */
export function recencyWeight(j: Job, now = Date.now()): number {
  // An unknown date must not be treated as an old one. For a posting with no
  // source-provided posted_date whose only first_seen is the corpus import
  // baseline, demoting it to 0.75 would be ranking on a timestamp we created
  // during a migration, not on anything about the job.
  if (j.posted_date_known !== true && j.first_seen_is_bulk) return 1
  const days = (now - effectiveDate(j)) / 86_400_000
  if (!Number.isFinite(days) || days <= 7) return 1
  if (days >= 90) return 0.75
  // Linear between the two, which is easier to reason about than a curve when a
  // ranking surprises you.
  return 1 - 0.25 * ((days - 7) / 83)
}

const byFit = (pick: (j: Job) => number) => (a: Job, b: Job) =>
  pick(b) * recencyWeight(b) - pick(a) * recencyWeight(a)

const SORTERS: Record<string, (a: Job, b: Job) => number> = {
  new_grad_fit: byFit((j) => j.new_grad_fit ?? 0),
  match_score: byFit((j) => j.match_score ?? 0),
  experienced_fit: byFit((j) => j.experienced_fit ?? 0),
  posted_date: (a, b) => effectiveDate(b) - effectiveDate(a),
  first_seen_at: (a, b) =>
    Date.parse(String(b.first_seen_at)) - Date.parse(String(a.first_seen_at)),
  company: (a, b) => String(a.company).localeCompare(String(b.company)),
  job_title: (a, b) => String(a.job_title).localeCompare(String(b.job_title)),
}

export interface QueryResult {
  items: Job[]
  total_count: number
  page: number
  limit: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export function queryJobs(
  all: Job[],
  f: Filters,
  page = 1,
  limit = 50,
  bodies?: Record<string, string>,
): QueryResult {
  const kw = (f.keyword || '').trim()
  let rows = all.filter((j) => matchesFilters(j, f, bodies))

  const sortBy = f.sort_by || 'new_grad_fit'
  const primary = SORTERS[sortBy] || SORTERS.new_grad_fit
  rows.sort((a, b) => {
    // With a query, relevance leads — unless the user explicitly picked a sort,
    // in which case that wins and relevance becomes the tiebreaker.
    if (kw && sortBy === 'new_grad_fit') {
      const r = keywordRank(b, kw) - keywordRank(a, kw)
      if (r) return r
    }
    const p = primary(a, b)
    if (p) return p
    if (kw) {
      const r = keywordRank(b, kw) - keywordRank(a, kw)
      if (r) return r
    }
    return (b.match_score ?? 0) - (a.match_score ?? 0)
  })

  // One card per company+role. Siblings are real, separately-applicable reqs, so
  // nothing is dropped — the survivor carries the count and the rest stay
  // reachable through it.
  if (f.group_roles !== false) {
    const seen = new Map<string, Job>()
    const order: string[] = []
    for (const j of rows) {
      const key = `${lc(j.company)}|${lc(j.normalized_title || j.job_title)}`
      const hit = seen.get(key)
      if (hit) {
        hit.group_count = (hit.group_count ?? 1) + 1
      } else {
        seen.set(key, { ...j, group_count: 1 })
        order.push(key)
      }
    }
    rows = order.map((k) => seen.get(k)!)
  }

  const total = rows.length
  const total_pages = Math.max(1, Math.ceil(total / limit))
  const start = (page - 1) * limit
  return {
    items: rows.slice(start, start + limit),
    total_count: total,
    page,
    limit,
    total_pages,
    has_next: page < total_pages,
    has_prev: page > 1,
  }
}

/** Sibling requisitions for the same role at other sites. */
export function siblingsOf(all: Job[], job: Job): Job[] {
  const key = `${lc(job.company)}|${lc(job.normalized_title || job.job_title)}`
  return all.filter(
    (j) => j.id !== job.id && `${lc(j.company)}|${lc(j.normalized_title || j.job_title)}` === key,
  )
}
