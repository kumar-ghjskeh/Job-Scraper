export interface Job {
  id: number
  company: string
  company_category: string
  company_priority: string

  job_title: string
  normalized_title: string
  role_category: string
  experience_level: string

  is_entry_level: boolean
  is_candidate_friendly: boolean
  is_senior: boolean
  years_required_min: number | null
  years_required_max: number | null

  location: string
  location_raw: string
  remote_status: string
  is_usa: boolean
  is_remote_usa: boolean
  country: string
  state: string
  city: string
  location_confidence: number

  job_id_from_company: string
  apply_url: string
  safe_apply_url: string
  original_apply_url: string
  apply_url_status: string
  apply_url_reason: string
  source_url: string
  ats_platform: string

  posted_date: string | null
  first_seen_at: string
  last_seen_at: string
  removed_at: string | null

  active_status: string
  missed_scrapes: number

  match_score: number
  matched_keywords: string
  score_breakdown_json: string
  relevance_score_label: string

  description_snippet: string
  full_description_text: string
  cleaned_description: string

  application_status: string
  notes: string
  resume_version_used: string
  saved_at: string | null
  applied_at: string | null
  ignored_at: string | null

  // Enrichment fields
  role_flags_json: string
  is_software_only: boolean
  is_hardware_software_codesign: boolean
  relevance_reason: string
  exclusion_reason: string
  matched_positive_terms_json: string
  data_quality_status: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total_count: number
  page: number
  limit: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export interface Company {
  id: number
  name: string
  category: string
  priority: string
  careers_url: string
  company_search_url: string
  ats_platform: string
  enabled: boolean
  last_scraped_at: string | null
  scrape_error_count: number
  notes: string
  total_active_jobs?: number
  relevant_active_jobs?: number
  viewable_jobs?: number
  usa_active_jobs?: number
  entry_level_jobs?: number
  new_jobs_today?: number
  scrape_status?: string
}

export interface JobFacets {
  role_categories: { value: string; count: number }[]
  priorities: { value: string; count: number }[]
  remote_statuses: { value: string; count: number }[]
  states: { value: string; count: number }[]
  entry_level_count: number
  candidate_friendly_count: number
  senior_count: number
  remote_count: number
  new_24h_count: number
}

export interface ScrapeRun {
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

export interface AnalyticsSummary {
  total_active: number
  new_24h: number
  entry_level_count: number
  usa_count: number
  remote_count: number
  high_score_count: number
  saved_count: number
  applied_count: number
  total_companies: number
  last_run: ScrapeRun | null
}

export interface Filters {
  status?: string
  company?: string
  priority?: string
  role_category?: string
  experience_level?: string
  remote?: string
  min_score?: number
  new_since_hours?: number
  keyword?: string
  usa_only?: boolean
  include_senior?: boolean
  include_software?: boolean
  include_adjacent?: boolean
  view?: string
  role_flags?: string
  is_entry_level?: boolean
  state?: string
  sort_by?: string
  sort_order?: string
}
