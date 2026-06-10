import type { Job } from './types'

export interface JobGroup {
  job: Job              // canonical (highest-scoring) posting for the role
  extraLocations: string[]  // additional USA locations of the same role
}

/**
 * Collapse postings that are the same role at one company but differ only by
 * location into a single canonical card, so the list isn't padded with
 * duplicates (e.g. "DV Engineer – SoC" at Etched in both San Jose and Austin).
 * Grouping key = company + normalized title.
 */
export function groupByCanonical(jobs: Job[]): JobGroup[] {
  const groups = new Map<string, Job[]>()
  const order: string[] = []

  for (const j of jobs) {
    const title = (j.normalized_title || j.job_title || '').toLowerCase().trim()
    const key = `${j.company.toLowerCase().trim()}|${title}`
    if (!groups.has(key)) { groups.set(key, []); order.push(key) }
    groups.get(key)!.push(j)
  }

  return order.map((key) => {
    const items = groups.get(key)!
    items.sort((a, b) => b.match_score - a.match_score)
    const primary = items[0]
    const locations = Array.from(
      new Set(items.map((i) => i.location).filter((l): l is string => !!l && l.trim().length > 0))
    )
    const extraLocations = locations.filter((l) => l !== primary.location)
    return { job: primary, extraLocations }
  })
}
