import axios from 'axios'
import type { AnalyticsSummary, Company, Filters, Job, JobFacets, PaginatedResponse, ScrapeRun } from './types'

// Local dev → Vite proxies '/api' to http://localhost:8000.
// Production → set VITE_API_BASE to your Render backend URL in Vercel.
const BASE = import.meta.env.VITE_API_BASE
  ? `${(import.meta.env.VITE_API_BASE as string).replace(/\/$/, '')}`
  : '/api'

function clean(params: Record<string, unknown>) {
  Object.keys(params).forEach((k) => {
    if (params[k] === undefined || params[k] === '' || params[k] === null) delete params[k]
  })
  return params
}

export const api = {
  async getJobs(filters: Filters = {}, page = 1, limit = 25): Promise<PaginatedResponse<Job>> {
    const params = clean({ page, limit, ...filters } as Record<string, unknown>)
    const { data } = await axios.get(`${BASE}/jobs`, { params })
    return data
  },

  async getEntryLevelJobs(filters: Filters = {}, page = 1, limit = 25): Promise<PaginatedResponse<Job>> {
    const params = clean({ page, limit, ...filters } as Record<string, unknown>)
    const { data } = await axios.get(`${BASE}/jobs/entry-level`, { params })
    return data
  },

  async getBestJobs(filters: Filters = {}, page = 1, limit = 25): Promise<PaginatedResponse<Job>> {
    const params = clean({ page, limit, min_score: 65, ...filters } as Record<string, unknown>)
    const { data } = await axios.get(`${BASE}/jobs/best`, { params })
    return data
  },

  async getSavedJobs(page = 1, limit = 25): Promise<PaginatedResponse<Job>> {
    const { data } = await axios.get(`${BASE}/jobs/saved`, { params: { page, limit } })
    return data
  },

  async getAppliedJobs(page = 1, limit = 25): Promise<PaginatedResponse<Job>> {
    const { data } = await axios.get(`${BASE}/jobs/applied`, { params: { page, limit } })
    return data
  },

  async updateJobStatus(
    id: number,
    update: { active_status?: string; application_status?: string; notes?: string }
  ): Promise<void> {
    await axios.patch(`${BASE}/jobs/${id}/status`, update)
  },

  async getJob(id: number): Promise<Job> {
    const { data } = await axios.get(`${BASE}/jobs/${id}`)
    return data
  },

  async getCompanies(): Promise<Company[]> {
    const { data } = await axios.get(`${BASE}/companies`)
    return data
  },

  async getScrapeRuns(): Promise<ScrapeRun[]> {
    const { data } = await axios.get(`${BASE}/scrape-runs`)
    return data
  },

  async triggerScrape(): Promise<void> {
    await axios.post(`${BASE}/scrape/run-now`)
  },

  async getAnalytics(): Promise<AnalyticsSummary> {
    const { data } = await axios.get(`${BASE}/analytics/summary`)
    return data
  },

  async getScrapeHealth() {
    const { data } = await axios.get(`${BASE}/scrape-health`)
    return data
  },

  async getScrapeErrors() {
    const { data } = await axios.get(`${BASE}/scrape-errors`)
    return data
  },

  async getFacets(usaOnly = true, includeSoftware = false): Promise<JobFacets> {
    const { data } = await axios.get(`${BASE}/jobs/facets`, {
      params: { usa_only: usaOnly, include_software: includeSoftware },
    })
    return data
  },

  async getSearchSuggestions(q: string): Promise<string[]> {
    if (!q || q.length < 2) return []
    const { data } = await axios.get(`${BASE}/jobs/search-suggestions`, { params: { q } })
    return data.suggestions || []
  },
}
