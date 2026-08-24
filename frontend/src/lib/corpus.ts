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
  last_scraped_at: string | null
  scrape_error_count: number
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
