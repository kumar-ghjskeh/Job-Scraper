import { useCallback, useEffect, useRef, useState } from 'react'
import './index.css'
import { CompaniesPage } from './components/CompaniesPage'
import { FilterSidebar } from './components/FilterSidebar'
import { JobCard } from './components/JobCard'
import { JobDetailsPanel } from './components/JobDetailsPanel'
import { Pagination } from './components/Pagination'
import { ScrapeHealth } from './components/ScrapeHealth'
import { SummaryCards } from './components/SummaryCards'
import { TopNav, type Tab } from './components/TopNav'
import { Icon } from './components/Icon'
import { api } from './lib/api'
import type { AnalyticsSummary, Filters, Job, PaginatedResponse } from './lib/types'

const PAGE_SIZE = 50

function SkeletonCard() {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '15px 16px',
    }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <div className="skeleton" style={{ width: 44, height: 44, borderRadius: 9, flexShrink: 0 }} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="skeleton" style={{ height: 16, borderRadius: 4, width: '70%' }} />
          <div className="skeleton" style={{ height: 12, borderRadius: 4, width: '40%' }} />
        </div>
        <div className="skeleton" style={{ width: 50, height: 50, borderRadius: '50%', flexShrink: 0 }} />
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
        {[60, 80, 70].map((w, i) => (
          <div key={i} className="skeleton" style={{ height: 22, width: w, borderRadius: 4 }} />
        ))}
      </div>
    </div>
  )
}

function EmptyState({ tab }: { tab: Tab }) {
  const msgs: Partial<Record<Tab, { title: string; sub: string }>> = {
    'entry-level': {
      title: 'No entry-level jobs found',
      sub: 'Try adjusting your filters or run a fresh scrape to fetch new postings.',
    },
    'best': {
      title: 'No high-score matches yet',
      sub: 'Run a scrape to fetch the latest RTL/DV postings and score them.',
    },
    'saved': {
      title: 'No saved jobs',
      sub: 'Click the bookmark icon on any job card to save it for later.',
    },
    'applied': {
      title: 'No applied jobs',
      sub: "Mark jobs as 'Applied' to track your applications here.",
    },
    'all': {
      title: 'No jobs found',
      sub: 'Try adjusting your filters or broadening your search.',
    },
  }
  const msg = msgs[tab] || { title: 'No results', sub: 'Try changing your filters.' }

  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '56px 24px', textAlign: 'center',
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: '50%', background: 'var(--surface-sunken)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px',
      }}>
        <Icon name="search" size={26} color="var(--text-faint)" />
      </div>
      <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
        {msg.title}
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 360, margin: '0 auto' }}>
        {msg.sub}
      </div>
    </div>
  )
}

function ListHeader({
  tab, loading, total, page, totalPages,
}: {
  tab: Tab; loading: boolean; total: number; page: number; totalPages: number
}) {
  const tabLabels: Partial<Record<Tab, string>> = {
    'entry-level': 'Entry-Level & Candidate Friendly',
    'best': 'Best Matches (Score ≥ 65)',
    'saved': 'Saved by You',
    'applied': 'Applied by You',
    'all': 'All Relevant Jobs',
  }

  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: 10,
    }}>
      <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
        {loading ? (
          <span>Loading…</span>
        ) : (
          <span>
            <strong style={{ color: 'var(--text)', fontWeight: 700 }}>{total.toLocaleString()}</strong>
            {' '}jobs · {tabLabels[tab] || ''}
          </span>
        )}
      </div>
      {total > 0 && totalPages > 1 && (
        <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>
          Page {page} of {totalPages}
        </span>
      )}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState<Tab>('entry-level')
  const [page, setPage] = useState(1)
  const [paginatedJobs, setPaginatedJobs] = useState<PaginatedResponse<Job> | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)
  const [filters, setFilters] = useState<Filters>({ usa_only: true, include_senior: false })
  const [search, setSearch] = useState('')
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const jobListRef = useRef<HTMLDivElement>(null)

  const loadAnalytics = useCallback(async () => {
    try { setAnalytics(await api.getAnalytics()) } catch { /* non-fatal */ }
  }, [])

  const loadJobs = useCallback(async () => {
    if (['companies', 'health'].includes(tab)) return
    setLoading(true)
    setError(null)
    try {
      let data: PaginatedResponse<Job>
      switch (tab) {
        case 'entry-level':
          data = await api.getEntryLevelJobs(filters, page, PAGE_SIZE)
          break
        case 'best':
          data = await api.getBestJobs(filters, page, PAGE_SIZE)
          break
        case 'saved':
          data = await api.getSavedJobs(page, PAGE_SIZE)
          break
        case 'applied':
          data = await api.getAppliedJobs(page, PAGE_SIZE)
          break
        default:
          data = await api.getJobs(filters, page, PAGE_SIZE)
      }
      setPaginatedJobs(data)
      if (selectedJob) {
        const updated = data.items.find((j) => j.id === selectedJob.id)
        if (updated) setSelectedJob(updated)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [tab, filters, page, selectedJob])

  useEffect(() => {
    loadJobs()
    loadAnalytics()
  }, [tab, filters, page]) // eslint-disable-line react-hooks/exhaustive-deps

  function changeTab(t: Tab) {
    setTab(t)
    setPage(1)
    setSelectedJob(null)
  }

  function changeFilters(f: Filters) {
    setFilters(f)
    setPage(1)
  }

  function handleSearch(q: string) {
    setSearch(q)
    setFilters((prev) => ({ ...prev, keyword: q || undefined }))
    setPage(1)
    if (q && ['companies', 'health'].includes(tab)) setTab('all')
  }

  function viewCompanyJobs(companyName: string) {
    setFilters({ ...filters, company: companyName })
    setTab('all')
    setPage(1)
    setSelectedJob(null)
  }

  function changePage(p: number) {
    setPage(p)
    jobListRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function handleRunScrape() {
    setRunning(true)
    try {
      await api.triggerScrape()
      setTimeout(() => { setRunning(false); loadJobs(); loadAnalytics() }, 10000)
    } catch { setRunning(false) }
  }

  async function handleQuickAction(job: Job, action: 'saved' | 'applied' | 'ignored') {
    const newStatus = job.active_status === action ? 'active' : action
    await api.updateJobStatus(job.id, { active_status: newStatus })
    loadJobs()
    loadAnalytics()
  }

  const showSidebar = !['companies', 'health', 'saved', 'applied'].includes(tab)
  const showPanel = selectedJob !== null
  const jobs = paginatedJobs?.items ?? []

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <TopNav
        activeTab={tab}
        onTabChange={changeTab}
        analytics={analytics}
        onRunScrape={handleRunScrape}
        running={running}
        search={search}
        onSearch={handleSearch}
      />

      <main style={{ maxWidth: 1680, margin: '0 auto', padding: '16px 20px 48px' }}>

        {/* Error banner */}
        {error && (
          <div style={{
            background: 'var(--error-light)', border: '1px solid var(--error-border)',
            borderRadius: 8, padding: '10px 16px', marginBottom: 14,
            color: 'var(--error)', fontSize: 13,
          }}>
            {error} — is the backend running on port 8000?
          </div>
        )}

        {/* Summary cards */}
        {!['companies', 'health'].includes(tab) && (
          <SummaryCards analytics={analytics} />
        )}

        {/* Page content */}
        {tab === 'companies' ? (
          <CompaniesPage onViewJobs={viewCompanyJobs} />
        ) : tab === 'health' ? (
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 10, padding: '20px 24px',
          }}>
            <ScrapeHealth />
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>

            {/* Left: Filter sidebar */}
            {showSidebar && (
              <FilterSidebar
                filters={filters}
                onChange={changeFilters}
                totalCount={paginatedJobs?.total_count ?? 0}
              />
            )}

            {/* Center: Job feed */}
            <div style={{ flex: 1, minWidth: 0 }} ref={jobListRef}>
              <ListHeader
                tab={tab}
                loading={loading}
                total={paginatedJobs?.total_count ?? 0}
                page={paginatedJobs?.page ?? 1}
                totalPages={paginatedJobs?.total_pages ?? 1}
              />

              {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
                </div>
              ) : jobs.length === 0 ? (
                <EmptyState tab={tab} />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }} className="animate-in">
                  {jobs.map((job) => (
                    <JobCard
                      key={job.id}
                      job={job}
                      selected={selectedJob?.id === job.id}
                      onClick={() => setSelectedJob(selectedJob?.id === job.id ? null : job)}
                      onQuickAction={(action) => handleQuickAction(job, action)}
                    />
                  ))}
                </div>
              )}

              {paginatedJobs && paginatedJobs.total_pages > 1 && (
                <Pagination
                  page={paginatedJobs.page}
                  totalPages={paginatedJobs.total_pages}
                  totalCount={paginatedJobs.total_count}
                  limit={PAGE_SIZE}
                  hasNext={paginatedJobs.has_next}
                  hasPrev={paginatedJobs.has_prev}
                  onPageChange={changePage}
                />
              )}
            </div>

            {/* Right: Job details panel */}
            {showPanel && (
              <JobDetailsPanel
                job={selectedJob}
                onClose={() => setSelectedJob(null)}
                onUpdate={() => { loadJobs(); loadAnalytics() }}
              />
            )}
          </div>
        )}
      </main>
    </div>
  )
}
