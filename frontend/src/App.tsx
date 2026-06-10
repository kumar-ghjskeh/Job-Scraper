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
import { groupByCanonical } from './lib/dedupe'
import { useTheme } from './lib/theme'
import { api } from './lib/api'
import type { AnalyticsSummary, Filters, Job, PaginatedResponse } from './lib/types'

const PAGE_SIZE = 50

const TAB_LABELS: Partial<Record<Tab, string>> = {
  'all': 'verified USA VLSI jobs',
  'entry-level': 'new-grad & entry-level jobs',
  'best': 'high-fit jobs',
  'saved': 'saved jobs',
  'applied': 'applied jobs',
}

function SkeletonCard() {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: '15px 16px' }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <div className="skeleton" style={{ width: 46, height: 46, borderRadius: 10, flexShrink: 0 }} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="skeleton" style={{ height: 16, borderRadius: 4, width: '70%' }} />
          <div className="skeleton" style={{ height: 12, borderRadius: 4, width: '40%' }} />
        </div>
        <div className="skeleton" style={{ width: 52, height: 52, borderRadius: '50%', flexShrink: 0 }} />
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
        {[60, 80, 70].map((w, i) => <div key={i} className="skeleton" style={{ height: 22, width: w, borderRadius: 4 }} />)}
      </div>
    </div>
  )
}

function EmptyState({ tab }: { tab: Tab }) {
  const msgs: Partial<Record<Tab, { title: string; sub: string }>> = {
    'entry-level': { title: 'No new-grad jobs match your filters', sub: 'Try widening filters or refresh jobs to pull the latest postings.' },
    'saved': { title: 'No saved jobs', sub: 'Click the bookmark icon on any job to save it for later.' },
    'applied': { title: 'No applied jobs', sub: "Mark jobs as 'Applied' to track your applications here." },
    'all': { title: 'No jobs match your filters', sub: 'Try widening your filters or clearing the search.' },
  }
  const msg = msgs[tab] || { title: 'No results', sub: 'Try changing your filters.' }
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: '56px 24px', textAlign: 'center' }}>
      <div style={{
        width: 56, height: 56, borderRadius: '50%', background: 'var(--surface-muted)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px',
      }}>
        <Icon name="search" size={26} color="var(--text-tertiary)" />
      </div>
      <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>{msg.title}</div>
      <div style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 360, margin: '0 auto' }}>{msg.sub}</div>
    </div>
  )
}

function ResultsSummary({ tab, loading, total, page, totalPages, analytics }: {
  tab: Tab; loading: boolean; total: number; page: number; totalPages: number; analytics: AnalyticsSummary | null
}) {
  const label = TAB_LABELS[tab] || 'jobs'
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontSize: 15, color: 'var(--text-primary)' }}>
          {loading ? <span style={{ color: 'var(--text-secondary)' }}>Loading…</span> : (
            <><strong style={{ fontWeight: 800 }}>{total.toLocaleString()}</strong> <span style={{ color: 'var(--text-secondary)' }}>{label}</span></>
          )}
        </div>
        {total > 0 && totalPages > 1 && (
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Page {page} of {totalPages}</span>
        )}
      </div>
      {!loading && analytics && total > 0 && (
        <div style={{ display: 'flex', gap: 14, marginTop: 6, flexWrap: 'wrap', fontSize: 12, color: 'var(--text-secondary)' }}>
          <span><strong style={{ color: 'var(--success)' }}>{analytics.new_24h}</strong> new today</span>
          <span><strong style={{ color: 'var(--accent-gold)' }}>{analytics.high_score_count}</strong> high-fit</span>
          <span><strong style={{ color: 'var(--primary)' }}>{analytics.entry_level_count}</strong> new-grad</span>
          <span><strong style={{ color: 'var(--text-primary)' }}>{analytics.total_companies}</strong> companies tracked</span>
        </div>
      )}
    </div>
  )
}

function ResumePlaceholder() {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10,
      padding: '56px 28px', textAlign: 'center', maxWidth: 620, margin: '8px auto',
    }}>
      <div style={{
        width: 60, height: 60, borderRadius: 14, background: 'var(--primary-light)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 18px',
      }}>
        <Icon name="fileText" size={28} color="var(--primary)" />
      </div>
      <div style={{ fontSize: 19, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 8 }}>Resume Matches</div>
      <div style={{ fontSize: 13.5, color: 'var(--text-secondary)', lineHeight: 1.65, maxWidth: 460, margin: '0 auto 20px' }}>
        Upload your resume to score every job by how well it fits your skills, see your matched
        and missing skills per role, and get a recommended resume version to apply with.
      </div>
      <button className="btn btn-primary" disabled style={{ padding: '9px 20px' }}>
        <Icon name="fileText" size={15} color="var(--on-primary)" /> Resume upload — coming soon
      </button>
    </div>
  )
}

export default function App() {
  const { theme, toggle: toggleTheme } = useTheme()
  const [tab, setTab] = useState<Tab>('all')
  const [page, setPage] = useState(1)
  const [paginatedJobs, setPaginatedJobs] = useState<PaginatedResponse<Job> | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)
  const [filters, setFilters] = useState<Filters>({ usa_only: true, include_senior: false })
  const [search, setSearch] = useState('')
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const jobListRef = useRef<HTMLDivElement>(null)

  const NO_FETCH: Tab[] = ['companies', 'health', 'resume']

  const loadAnalytics = useCallback(async () => {
    try { setAnalytics(await api.getAnalytics()) } catch { /* non-fatal */ }
  }, [])

  const loadJobs = useCallback(async () => {
    if (NO_FETCH.includes(tab)) return
    setLoading(true)
    setError(null)
    try {
      let data: PaginatedResponse<Job>
      switch (tab) {
        case 'entry-level': data = await api.getEntryLevelJobs(filters, page, PAGE_SIZE); break
        case 'best':        data = await api.getBestJobs(filters, page, PAGE_SIZE); break
        case 'saved':       data = await api.getSavedJobs(page, PAGE_SIZE); break
        case 'applied':     data = await api.getAppliedJobs(page, PAGE_SIZE); break
        default:            data = await api.getJobs(filters, page, PAGE_SIZE)
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

  function changeTab(t: Tab) { setTab(t); setPage(1); setSelectedJob(null) }
  function changeFilters(f: Filters) { setFilters(f); setPage(1) }

  function handleSearch(q: string) {
    setSearch(q)
    setFilters((prev) => ({ ...prev, keyword: q || undefined }))
    setPage(1)
    if (q && NO_FETCH.includes(tab)) setTab('all')
  }

  function viewCompanyJobs(companyName: string) {
    setFilters({ ...filters, company: companyName })
    setTab('all'); setPage(1); setSelectedJob(null)
  }

  function changePage(p: number) {
    setPage(p)
    jobListRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await api.triggerScrape()
      setTimeout(() => { setRefreshing(false); loadJobs(); loadAnalytics() }, 10000)
    } catch { setRefreshing(false) }
  }

  async function handleQuickAction(job: Job, action: 'saved' | 'applied' | 'ignored') {
    const newStatus = job.active_status === action ? 'active' : action
    await api.updateJobStatus(job.id, { active_status: newStatus })
    loadJobs(); loadAnalytics()
  }

  const showSidebar = !['companies', 'health', 'saved', 'applied', 'resume'].includes(tab)
  const showPanel = selectedJob !== null
  const jobs = paginatedJobs?.items ?? []
  // Collapse multi-location duplicates of the same role into one canonical card.
  const grouped = groupByCanonical(jobs)

  return (
    <div style={{ minHeight: '100vh', background: 'var(--background)' }}>
      <TopNav
        activeTab={tab}
        onTabChange={changeTab}
        analytics={analytics}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        search={search}
        onSearch={handleSearch}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <main style={{ maxWidth: 1680, margin: '0 auto', padding: '16px 20px 48px' }}>
        {error && (
          <div style={{
            background: 'var(--warning-light)', border: '1px solid var(--warning-border)',
            borderRadius: 8, padding: '10px 16px', marginBottom: 14, color: 'var(--warning)', fontSize: 13,
          }}>
            Data sync delayed — last update may be stale. Retrying automatically. ({error})
          </div>
        )}

        {!['companies', 'health', 'resume'].includes(tab) && <SummaryCards analytics={analytics} />}

        {tab === 'companies' ? (
          <CompaniesPage onViewJobs={viewCompanyJobs} />
        ) : tab === 'health' ? (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '20px 24px' }}>
            <ScrapeHealth />
          </div>
        ) : tab === 'resume' ? (
          <ResumePlaceholder />
        ) : (
          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
            {showSidebar && (
              <FilterSidebar filters={filters} onChange={changeFilters} totalCount={paginatedJobs?.total_count ?? 0} />
            )}

            <div style={{ flex: 1, minWidth: 0 }} ref={jobListRef}>
              <ResultsSummary
                tab={tab} loading={loading} analytics={analytics}
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
                  {grouped.map((g) => (
                    <JobCard
                      key={g.job.id}
                      job={g.job}
                      extraLocations={g.extraLocations}
                      selected={selectedJob?.id === g.job.id}
                      onClick={() => setSelectedJob(selectedJob?.id === g.job.id ? null : g.job)}
                      onQuickAction={(action) => handleQuickAction(g.job, action)}
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

            {showPanel && (
              <JobDetailsPanel job={selectedJob} onClose={() => setSelectedJob(null)} onUpdate={() => { loadJobs(); loadAnalytics() }} />
            )}
          </div>
        )}
      </main>
    </div>
  )
}
