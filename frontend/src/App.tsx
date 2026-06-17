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
import { ResumeIntel } from './components/ResumeIntel'
import { groupByCanonical } from './lib/dedupe'
import { useTheme } from './lib/theme'
import { useIsMobile } from './lib/useIsMobile'
import { api } from './lib/api'
import type { AnalyticsSummary, Filters, Job, PaginatedResponse } from './lib/types'

const PAGE_SIZE = 50

const TAB_LABELS: Partial<Record<Tab, string>> = {
  'all': 'verified jobs',
  'resume': 'jobs ranked by resume match',
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

function EmptyState({ tab, query }: { tab: Tab; query?: string }) {
  // Active company/keyword search that returned nothing → likely an untracked
  // company (e.g. AMD). Be explicit and offer a direct careers search.
  if (query && query.trim() && ['all', 'best', 'entry-level'].includes(tab)) {
    const q = query.trim()
    const careers = `https://www.google.com/search?q=${encodeURIComponent(`${q} RTL OR "design verification" OR ASIC jobs careers`)}`
    return (
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: '52px 24px', textAlign: 'center' }}>
        <div style={{
          width: 56, height: 56, borderRadius: '50%', background: 'var(--surface-muted)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px',
        }}>
          <Icon name="search" size={26} color="var(--text-tertiary)" />
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
          No tracked jobs match “{q}”
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 420, margin: '0 auto 16px', lineHeight: 1.6 }}>
          We may not track this company yet, or it has no open RTL/DV roles right now.
          You can search their careers site directly.
        </div>
        <a href={careers} target="_blank" rel="noopener noreferrer" className="btn btn-outline" style={{ textDecoration: 'none' }}>
          Search “{q}” roles directly <Icon name="external" size={14} />
        </a>
      </div>
    )
  }
  const msgs: Partial<Record<Tab, { title: string; sub: string }>> = {
    'entry-level': { title: 'No new-grad jobs match your filters', sub: 'Try widening filters or refresh jobs to pull the latest postings.' },
    'saved': { title: 'No saved jobs', sub: 'Click the bookmark icon on any job to save it for later.' },
    'applied': { title: 'No applied jobs', sub: "Mark jobs as 'Applied' to track your applications here." },
    'all': { title: 'No jobs match your filters', sub: 'Try widening your filters or clearing the search.' },
    'resume': { title: 'Upload your resume to see matches', sub: 'Use the panel on the left to upload your resume — every job will be ranked by how well it fits you.' },
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {(tab === 'applied' || tab === 'saved') && total > 0 && (
            <a href={api.applicationsCsvUrl()} download
              style={{ fontSize: 12, fontWeight: 700, color: 'var(--primary)', display: 'inline-flex', alignItems: 'center', gap: 4, textDecoration: 'none' }}>
              <Icon name="external" size={12} color="var(--primary)" /> Export CSV
            </a>
          )}
          {total > 0 && totalPages > 1 && (
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Page {page} of {totalPages}</span>
          )}
        </div>
      </div>
      {!loading && analytics && total > 0 && (
        <div style={{ display: 'flex', gap: 14, marginTop: 6, flexWrap: 'wrap', fontSize: 12, color: 'var(--text-secondary)' }}>
          <span><strong style={{ color: 'var(--success)' }}>{analytics.new_24h}</strong> new today</span>
          <span><strong style={{ color: 'var(--accent-gold)' }}>{analytics.high_score_count}</strong> high-fit</span>
          <span><strong style={{ color: 'var(--primary)' }}>{analytics.strict_entry_count ?? analytics.entry_level_count}</strong> truly entry-level</span>
          <span><strong style={{ color: 'var(--text-primary)' }}>{analytics.total_companies}</strong> companies tracked</span>
        </div>
      )}
      {!loading && tab === 'entry-level' && analytics && (
        <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-tertiary)' }}>
          <strong style={{ color: 'var(--teal)' }}>{analytics.strict_entry_count ?? 0}</strong> explicitly entry-level ·{' '}
          <strong style={{ color: 'var(--primary)' }}>{analytics.candidate_friendly_count ?? 0}</strong> likely-junior (non-senior RTL/DV at top companies — check each job's seniority confidence)
        </div>
      )}
    </div>
  )
}

export default function App() {
  const { theme, toggle: toggleTheme } = useTheme()
  const isMobile = useIsMobile()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [tab, setTab] = useState<Tab>('all')
  const [page, setPage] = useState(1)
  const [paginatedJobs, setPaginatedJobs] = useState<PaginatedResponse<Job> | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)
  // Default shows every live role (incl. senior) — the New Grad tab + seniority
  // chips narrow it. include_senior stays true; the toggle was removed.
  const [filters, setFilters] = useState<Filters>({ usa_only: true, include_senior: true })
  const [search, setSearch] = useState('')
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [matchMap, setMatchMap] = useState<Record<string, { resume_match: number; apply_priority: string }>>({})
  // Default to New Grad Fit: for a new grad, "show me the roles I can realistically
  // get, best fit first" is the most intuitive ranking (a ng=100 New-College-Grad
  // role surfaces at the top instead of being buried by the resume-overlap blend).
  const [resumeSort, setResumeSort] = useState('new_grad_fit')
  const jobListRef = useRef<HTMLDivElement>(null)

  const NO_FETCH: Tab[] = ['companies', 'health']

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
        case 'resume':      data = await api.getResumeMatches(page, PAGE_SIZE, !!filters.include_senior, undefined, resumeSort, filters); break
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
      // Overlay resume-match badges on cards (other tabs) — one batch call.
      if (tab !== 'resume' && data.items.length) {
        api.getMatchBatch(data.items.map((j) => j.id)).then(setMatchMap).catch(() => setMatchMap({}))
      } else {
        setMatchMap({})
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
  }, [tab, filters, page, resumeSort]) // eslint-disable-line react-hooks/exhaustive-deps

  // Lock body scroll while a mobile drawer or full-screen sheet is open.
  const sheetOpen = isMobile && selectedJob !== null
  useEffect(() => {
    const lock = filtersOpen || sheetOpen
    document.body.style.overflow = lock ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [filtersOpen, sheetOpen])

  // Leaving mobile (e.g. rotate to landscape / resize) should dismiss the drawer.
  useEffect(() => { if (!isMobile) setFiltersOpen(false) }, [isMobile])

  // Keyboard navigation (desktop power-user): j/k or ↑/↓ move through jobs,
  // Enter/o open, Esc closes the panel, s saves, a marks applied. Ignored while
  // typing in a field.
  useEffect(() => {
    if (isMobile) return
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null
      if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const list = groupByCanonical(paginatedJobs?.items ?? []).map((g) => g.job)
      if (!list.length && e.key !== 'Escape') return
      const idx = selectedJob ? list.findIndex((j) => j.id === selectedJob.id) : -1
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault(); setSelectedJob(list[Math.min(list.length - 1, idx + 1)] ?? list[0])
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault(); setSelectedJob(idx <= 0 ? list[0] : list[idx - 1])
      } else if (e.key === 'Escape') {
        setSelectedJob(null)
      } else if (selectedJob && (e.key === 's' || e.key === 'a')) {
        e.preventDefault(); handleQuickAction(selectedJob, e.key === 's' ? 'saved' : 'applied')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isMobile, paginatedJobs, selectedJob]) // eslint-disable-line react-hooks/exhaustive-deps

  function changeTab(t: Tab) { setTab(t); setPage(1); setSelectedJob(null); setFiltersOpen(false) }
  function changeFilters(f: Filters) { setFilters(f); setPage(1) }

  function handleSearch(q: string) {
    setSearch(q)
    setFilters((prev) => ({ ...prev, keyword: q || undefined }))
    setPage(1)
    if (q && NO_FETCH.includes(tab)) setTab('all')
  }

  function viewCompanyJobs(companyName: string) {
    // Reset to the canonical All-Jobs view (+ this company) so the list shown
    // matches the card's "View N Jobs" count exactly — no stale keyword/level
    // filters carried over from a previous search.
    setFilters({ usa_only: true, include_senior: true, company: companyName })
    setSearch('')
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
      const prevId = (await api.getScrapeRuns().catch(() => []))[0]?.id
      await api.triggerScrape()
      // Poll the scrape run until it actually finishes (a scrape takes minutes —
      // the old fixed 10s reload showed stale counts), then refresh the list.
      const deadline = Date.now() + 7 * 60 * 1000
      const poll = async () => {
        try {
          const runs = (await api.getScrapeRuns()).sort((a, b) => (a.started_at < b.started_at ? 1 : -1))
          const latest = runs[0]
          if (latest && latest.id !== prevId && latest.finished_at) {
            setRefreshing(false); loadJobs(); loadAnalytics(); return
          }
        } catch { /* keep polling */ }
        if (Date.now() < deadline) setTimeout(poll, 4000)
        else { setRefreshing(false); loadJobs(); loadAnalytics() }
      }
      setTimeout(poll, 4000)
    } catch { setRefreshing(false) }
  }

  async function handleQuickAction(job: Job, action: 'saved' | 'applied' | 'ignored') {
    const newStatus = job.active_status === action ? 'active' : action
    await api.updateJobStatus(job.id, { active_status: newStatus })
    loadJobs(); loadAnalytics()
  }

  // Resume Matches gets the filter sidebar too (consistent filtering across tabs).
  const showSidebar = !['companies', 'health', 'saved', 'applied'].includes(tab)
  const showPanel = selectedJob !== null
  const activeFilterCount = Object.entries(filters).filter(([k, v]) => {
    if (k === 'usa_only' && v === true) return false
    if (k === 'include_senior' && v === false) return false
    return v !== undefined && v !== '' && v !== false
  }).length
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

      <main style={{ maxWidth: 1680, margin: '0 auto', padding: isMobile ? '12px 12px 40px' : '16px 20px 48px' }}>
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
        ) : (
          <div style={{ display: 'flex', gap: isMobile ? 12 : 16, alignItems: 'flex-start', flexDirection: isMobile ? 'column' : 'row' }}>
            {tab === 'resume' ? (
              // Resume Matches gets the SAME filters as every other tab (so filtering
              // is consistent), with the resume version/skill-gap rail stacked below.
              !isMobile && showSidebar ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flexShrink: 0 }}>
                  <FilterSidebar filters={filters} onChange={changeFilters} totalCount={paginatedJobs?.total_count ?? 0} hideSort />
                  <ResumeIntel onChanged={() => { loadJobs(); loadAnalytics() }} />
                </div>
              ) : (
                <ResumeIntel onChanged={() => { loadJobs(); loadAnalytics() }} />
              )
            ) : !isMobile && showSidebar ? (
              <FilterSidebar filters={filters} onChange={changeFilters} totalCount={paginatedJobs?.total_count ?? 0} />
            ) : null}

            <div style={{ flex: 1, minWidth: 0, width: isMobile ? '100%' : undefined }} ref={jobListRef}>
              {isMobile && showSidebar && (
                <div className="mobile-toolbar">
                  <button onClick={() => setFiltersOpen(true)}>
                    <Icon name="sliders" size={15} /> Filters
                    {activeFilterCount > 0 && (
                      <span className="pill pill-primary" style={{ fontSize: 10, fontWeight: 800, padding: '1px 7px' }}>{activeFilterCount}</span>
                    )}
                  </button>
                </div>
              )}
              <ResultsSummary
                tab={tab} loading={loading} analytics={analytics}
                total={paginatedJobs?.total_count ?? 0}
                page={paginatedJobs?.page ?? 1}
                totalPages={paginatedJobs?.total_pages ?? 1}
              />

              {tab === 'resume' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <span style={{ fontSize: 12.5, color: 'var(--text-secondary)', fontWeight: 600 }}>Sort by</span>
                  <select
                    value={resumeSort}
                    onChange={(e) => { setResumeSort(e.target.value); setPage(1) }}
                    style={{
                      background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8,
                      padding: '6px 10px', fontSize: 12.5, color: 'var(--text-primary)', outline: 'none', cursor: 'pointer',
                    }}
                  >
                    <option value="new_grad_fit">Best New Grad Fit</option>
                    <option value="match">Best match (overall)</option>
                    <option value="resume_match">Best Resume Match</option>
                    <option value="apply_priority">Apply Priority</option>
                    <option value="newest">Newest posted</option>
                    <option value="recent">Recently added</option>
                  </select>
                </div>
              )}

              {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
                </div>
              ) : jobs.length === 0 ? (
                <EmptyState tab={tab} query={filters.keyword} />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }} className="animate-in">
                  {grouped.map((g) => (
                    <JobCard
                      key={g.job.id}
                      job={g.job}
                      extraLocations={g.extraLocations}
                      resumeMatch={tab === 'resume' ? g.job.resume_match : matchMap[String(g.job.id)]?.resume_match}
                      resumePrimary={tab === 'resume'}
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

            {!isMobile && showPanel && (
              <JobDetailsPanel job={selectedJob} onClose={() => setSelectedJob(null)} onUpdate={() => { loadJobs(); loadAnalytics() }} />
            )}
          </div>
        )}
      </main>

      {/* ── Mobile: filters drawer ── */}
      {isMobile && filtersOpen && (
        <>
          <div className="mobile-backdrop" onClick={() => setFiltersOpen(false)} />
          <div className="mobile-drawer">
            <FilterSidebar
              mobile
              onClose={() => setFiltersOpen(false)}
              filters={filters}
              onChange={changeFilters}
              totalCount={paginatedJobs?.total_count ?? 0}
            />
          </div>
        </>
      )}

      {/* ── Mobile: job details full-screen sheet ── */}
      {isMobile && showPanel && (
        <div className="mobile-sheet">
          <JobDetailsPanel
            mobile
            job={selectedJob}
            onClose={() => setSelectedJob(null)}
            onUpdate={() => { loadJobs(); loadAnalytics() }}
          />
        </div>
      )}
    </div>
  )
}
