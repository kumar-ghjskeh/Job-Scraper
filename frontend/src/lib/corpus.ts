/**
 * The job corpus, served as a static file instead of queried from a database.
 *
 * The whole corpus is ~270 KB gzipped, so the browser fetches it once and then
 * filters, searches, sorts and paginates locally. That is faster than the round
 * trip it replaces (no cold start, no cross-country hop) and it removes the
 * component that repeatedly took this app down: a metered database whose free
 * transfer quota the app kept exhausting.
 *
 * Descriptions live in a second file, fetched lazily the first time a posting is
 * opened, so the initial load stays small.
 */
import type { Job } from './types'

export interface CorpusCompany {
  name: string
  category: string
  priority: string
  careers_url: string
  ats_platform: string
  engine: string
  enabled: boolean
  usa_active_jobs: number
  total_active_jobs: number
  viewable_jobs: number
  entry_level_jobs: number
  new_jobs_today: number
  parser_confidence: number
  /** True when the source is actually producing postings — the honest signal,
   *  rather than merely being listed in the config. */
  auto_connected: boolean
  scrape_status: string
  last_scraped_at: string | null
  scrape_error_count: number
  consecutive_empty_scrapes?: number
  quarantined?: boolean
}

export interface CorpusRun {
  id: number
  started_at: string
  finished_at: string | null
  companies_scraped: number
  jobs_found: number
  new_jobs: number
  removed_jobs: number
  errors: number
  triggered_by: string
}

export interface Corpus {
  generated_at: string
  count: number
  jobs: Job[]
  companies: CorpusCompany[]
  runs: CorpusRun[]
}

// Cache-busted per deploy so a fresh snapshot is picked up immediately, while
// repeat visits within a deploy are served from the browser cache.
const BUILD = (import.meta as { env?: Record<string, string> }).env?.VITE_BUILD_ID || ''
const JOBS_URL = `/data/jobs.json${BUILD ? `?v=${BUILD}` : ''}`
const DETAILS_URL = `/data/details.json${BUILD ? `?v=${BUILD}` : ''}`

let _corpus: Promise<Corpus> | null = null
let _details: Promise<Record<string, string>> | null = null

/** The corpus, fetched once per page load. */
export function loadCorpus(): Promise<Corpus> {
  if (!_corpus) {
    _corpus = fetch(JOBS_URL)
      .then((r) => {
        if (!r.ok) throw new Error(`corpus ${r.status}`)
        return r.json()
      })
      .then((d: Corpus) => {
        // Only ACTIVE postings are browseable. possibly_removed rows are carried
        // in the file so the scraper's miss counter survives a rebuild — they are
        // not jobs the user should see.
        d.jobs = (d.jobs || []).filter(
          (j) => String((j as unknown as Record<string, unknown>).active_status ?? 'active') === 'active',
        )
        markBulkImportedFirstSeen(d.jobs)
        d.count = d.jobs.length
        return d
      })
      .catch((e) => {
        _corpus = null // let a later call retry rather than caching the failure
        throw e
      })
  }
  return _corpus
}

/** Description bodies, fetched the first time a posting is opened. */
export function loadDetails(): Promise<Record<string, string>> {
  if (!_details) {
    _details = fetch(DETAILS_URL)
      .then((r) => (r.ok ? r.json() : { descriptions: {} }))
      .then((d: { descriptions?: Record<string, string> }) => d.descriptions || {})
      .catch(() => {
        _details = null
        return {}
      })
  }
  return _details
}

export function clearCorpusCache(): void {
  _corpus = null
  _details = null
}


/** Filter counts, computed from the corpus (was GET /jobs/facets). */
export async function facetsFromCorpus(usaOnly = true, includeSoftware = false) {
  const c = await loadCorpus()
  const hidden = ['Software / Compiler', 'Unknown', 'Adjacent / Backup']
  const rows = c.jobs.filter(
    (j) => (!usaOnly || j.is_usa) && (includeSoftware || !j.is_software_only)
      && !hidden.includes(j.role_category),
  )
  const tally = (pick: (j: typeof rows[number]) => string) => {
    const m = new Map<string, number>()
    for (const j of rows) {
      const v = pick(j)
      if (v) m.set(v, (m.get(v) || 0) + 1)
    }
    return [...m.entries()].map(([value, count]) => ({ value, count }))
      .sort((a, b) => b.count - a.count)
  }
  const dayAgo = Date.now() - 24 * 3600_000
  const eff = (j: typeof rows[number]) =>
    Date.parse(String((j.posted_date && j.posted_date_known !== false ? j.posted_date : null) || j.first_seen_at))
  return {
    role_categories: tally((j) => j.role_category),
    priorities: tally((j) => j.company_priority),
    remote_statuses: tally((j) => j.remote_status),
    states: tally((j) => j.state),
    entry_level_count: rows.filter((j) => j.is_entry_level || j.is_candidate_friendly).length,
    candidate_friendly_count: rows.filter((j) => j.is_candidate_friendly).length,
    senior_count: rows.filter((j) => j.is_senior).length,
    remote_count: rows.filter((j) => /remote/i.test(j.remote_status || '')).length,
    new_24h_count: rows.filter((j) => eff(j) >= dayAgo).length,
  }
}

/** Flag rows whose `first_seen_at` is the corpus's bulk-import baseline, not a real
 *  discovery date.
 *
 *  When the static corpus was first built, every job it contained got that day's
 *  timestamp: 936 of 1,793 active rows (52%) share 2026-08-24. For a posting with no
 *  source-provided posted_date, the UI then read that back as "Added 6w ago" — a
 *  discovery date that never happened — and the recency weight demoted it on the
 *  strength of it.
 *
 *  Detected rather than hardcoded, so it keeps working after the next rebuild: the
 *  EARLIEST first_seen date in the corpus, when it accounts for an implausible share
 *  of rows, is the import baseline. Jobs genuinely discovered on day one cannot be
 *  told apart from imported ones — on that day they ARE the import. Later spikes are
 *  left alone, which matters: 325 rows share 2026-10-01, the day five new companies
 *  came online, and that is real.
 */
export function markBulkImportedFirstSeen(jobs: Job[], shareThreshold = 0.25): void {
  const byDay = new Map<string, number>()
  for (const j of jobs) {
    const day = String(j.first_seen_at ?? '').slice(0, 10)
    if (day) byDay.set(day, (byDay.get(day) ?? 0) + 1)
  }
  if (!byDay.size) return
  const earliest = [...byDay.keys()].sort()[0]
  if ((byDay.get(earliest) ?? 0) / jobs.length < shareThreshold) return
  for (const j of jobs) {
    if (String(j.first_seen_at ?? '').slice(0, 10) === earliest) {
      j.first_seen_is_bulk = true
    }
  }
}

/** Typed, counted autocomplete suggestions (was GET /jobs/search-suggestions). */
export async function suggestionsFromCorpus(q: string, limit = 8) {
  const term = q.trim().toLowerCase()
  if (term.length < 2) return []
  const c = await loadCorpus()
  // Suggest only what a search can actually return. This filtered on is_usa and
  // is_software_only alone, so it drew on retired postings and on the categories
  // the default view hides — meaning it would offer a title (or "Physical Design")
  // and then the search for it came back empty, which reads as a broken search.
  // Same set as query.ts: a suggestion whose search returns nothing reads as a
  // broken search, so autocomplete must draw only on what the default view shows.
  const HIDDEN = new Set([
    'Software / Compiler', 'Unknown', 'Adjacent / Backup', 'Physical Design',
    'Post-Silicon Validation', 'DFT', 'EDA / Verification Tools',
  ])
  const rows = c.jobs.filter(
    (j) =>
      j.is_usa &&
      !j.is_software_only &&
      (j.active_status ?? 'active') === 'active' &&
      !HIDDEN.has(String(j.role_category)),
  )
  const bucket = (pick: (j: typeof rows[number]) => string, type: 'company' | 'title' | 'skill') => {
    const m = new Map<string, number>()
    for (const j of rows) {
      const v = (pick(j) || '').trim()
      if (v && v.toLowerCase().includes(term)) m.set(v, (m.get(v) || 0) + 1)
    }
    return [...m.entries()].map(([value, count]) => ({
      value, type, count,
      rank: value.toLowerCase().startsWith(term) ? 0 : 1,
    }))
  }
  const all = [
    ...bucket((j) => j.company, 'company').sort((a, b) => a.rank - b.rank || b.count - a.count).slice(0, 3),
    ...bucket((j) => j.job_title, 'title').sort((a, b) => a.rank - b.rank || b.count - a.count).slice(0, limit),
    ...bucket((j) => j.role_category, 'skill').sort((a, b) => a.rank - b.rank || b.count - a.count).slice(0, 3),
  ]
  const seen = new Set<string>()
  return all
    .filter((s) => {
      const k = s.value.toLowerCase()
      if (seen.has(k)) return false
      seen.add(k)
      return true
    })
    .sort((a, b) => Number(a.type !== 'company') - Number(b.type !== 'company') || b.count - a.count)
    .slice(0, limit)
    .map(({ value, type, count }) => ({ value, type, count }))
}
