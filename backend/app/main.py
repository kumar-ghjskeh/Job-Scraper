"""FastAPI application — RTL/DV Job Radar API."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, col, func, select

from .config import settings
from .database import get_session, init_db
from .models import ActiveStatus, Company, JobPosting, ScrapeError, ScrapeRun
from .scheduler import create_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RTL/DV Job Radar", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Allow any Vercel deployment (production + preview URLs) out of the box.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    from .config import load_companies
    from .database import engine
    with Session(engine) as session:
        for cfg in load_companies():
            existing = session.exec(select(Company).where(Company.name == cfg["name"])).first()
            if not existing:
                session.add(Company(
                    name=cfg["name"],
                    category=cfg.get("category", ""),
                    priority=cfg.get("priority", "C"),
                    careers_url=cfg.get("careers_url", ""),
                    company_search_url=cfg.get("company_search_url", ""),
                    ats_platform=cfg.get("ats_platform", "generic"),
                    enabled=cfg.get("enabled", True),
                ))
            else:
                # Update mutable config fields on existing company records
                existing.careers_url = cfg.get("careers_url", existing.careers_url)
                existing.company_search_url = cfg.get("company_search_url", getattr(existing, "company_search_url", ""))
                existing.enabled = cfg.get("enabled", existing.enabled)
                session.add(existing)
        session.commit()
    scheduler = create_scheduler()
    scheduler.start()

    # On a fresh cloud deploy, populate the database without waiting for the
    # first scheduled run. Empty DB → scrape; already-populated → skip.
    if settings.run_scrape_on_startup:
        import asyncio

        async def _initial_scrape():
            await asyncio.sleep(5)  # let the server finish coming up
            with Session(engine) as s:
                count = s.exec(select(func.count(JobPosting.id))).one()
            if count == 0:
                logger.info("Empty database on startup — running initial scrape")
                from .scrape_engine import run_scrape
                await run_scrape(triggered_by="startup")

        asyncio.create_task(_initial_scrape())


@app.on_event("shutdown")
async def shutdown():
    from .scheduler import get_scheduler
    s = get_scheduler()
    if s:
        s.shutdown(wait=False)


# ── Response models ────────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    id: int
    company: str
    company_category: str
    company_priority: str
    job_title: str
    normalized_title: str = ""
    role_category: str
    experience_level: str
    is_entry_level: bool
    is_candidate_friendly: bool
    is_senior: bool
    location: str
    location_raw: str = ""
    remote_status: str
    is_usa: bool
    is_remote_usa: bool
    country: str = ""
    state: str = ""
    city: str = ""
    location_confidence: float = 0.0
    match_score: int
    relevance_score_label: str = ""
    matched_keywords: str
    score_breakdown_json: str = ""
    active_status: str
    apply_url: str
    safe_apply_url: str = ""
    apply_url_status: str = ""
    apply_url_reason: str = ""
    original_apply_url: str = ""
    source_url: str = ""
    posted_date: Optional[datetime]
    first_seen_at: datetime
    last_seen_at: datetime
    removed_at: Optional[datetime]
    saved_at: Optional[datetime]
    applied_at: Optional[datetime]
    ignored_at: Optional[datetime] = None
    description_snippet: str
    full_description_text: str = ""
    cleaned_description: str = ""
    ats_platform: str
    notes: str
    application_status: str
    resume_version_used: str = ""
    years_required_min: Optional[int]
    years_required_max: Optional[int]
    job_id_from_company: str = ""
    missed_scrapes: int = 0
    # New enrichment fields
    role_flags_json: str = ""
    is_software_only: bool = False
    is_hardware_software_codesign: bool = False
    relevance_reason: str = ""
    exclusion_reason: str = ""
    matched_positive_terms_json: str = ""
    data_quality_status: str = ""
    # Eligibility / sponsorship (Phase 1)
    eligibility_risk: str = ""
    eligibility_terms: str = ""
    sponsors_h1b: Optional[bool] = None
    # Classification confidence & data quality (Phase 2)
    seniority_confidence: int = 0
    classification_confidence: int = 0
    data_quality_score: int = 0
    source_reliability: str = ""
    location_label: str = ""
    posted_date_known: bool = False

    model_config = {"from_attributes": True}


class PaginatedJobResponse(BaseModel):
    items: list[JobResponse]
    total_count: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool


class StatusUpdate(BaseModel):
    active_status: Optional[str] = None
    application_status: Optional[str] = None
    notes: Optional[str] = None
    resume_version_used: Optional[str] = None


class CompanyResponse(BaseModel):
    id: int
    name: str
    category: str
    priority: str
    careers_url: str
    company_search_url: str = ""
    ats_platform: str
    enabled: bool
    last_scraped_at: Optional[datetime]
    scrape_error_count: int
    notes: str = ""
    total_active_jobs: int = 0
    relevant_active_jobs: int = 0
    viewable_jobs: int = 0
    usa_active_jobs: int = 0
    entry_level_jobs: int = 0
    new_jobs_today: int = 0
    scrape_status: str = "unknown"

    model_config = {"from_attributes": True}


class ScrapeRunResponse(BaseModel):
    id: int
    started_at: datetime
    finished_at: Optional[datetime]
    companies_scraped: int
    jobs_found: int
    new_jobs: int
    removed_jobs: int
    errors: int
    triggered_by: str

    model_config = {"from_attributes": True}


# ── Session dep ────────────────────────────────────────────────────────────────

SessionDep = Annotated[Session, Depends(get_session)]
VALID_STATUSES = {s.value for s in ActiveStatus}


# ── Job filter builder ─────────────────────────────────────────────────────────

def _build_job_query(
    session: Session,
    status: Optional[str] = None,
    company: Optional[str] = None,
    company_ids: Optional[str] = None,
    priority: Optional[str] = None,
    role_category: Optional[str] = None,
    experience_level: Optional[str] = None,
    level_filter: Optional[str] = None,
    remote: Optional[str] = None,
    min_score: Optional[int] = None,
    new_since_hours: Optional[int] = None,
    first_seen_days: Optional[int] = None,
    keyword: Optional[str] = None,
    skills: Optional[str] = None,
    usa_only: bool = True,
    include_senior: bool = False,
    include_unknown_location: bool = True,
    include_software: bool = False,
    include_adjacent: bool = False,
    view: Optional[str] = None,
    role_flags: Optional[str] = None,
    state: Optional[str] = None,
    sort_by: str = "match_score",
    sort_order: str = "desc",
    page: int = 1,
    limit: int = 50,
) -> tuple[list[JobPosting], int]:

    stmt = select(JobPosting)
    conditions = []

    # Status filter (default: active only)
    target_status = status or ActiveStatus.active
    conditions.append(JobPosting.active_status == target_status)

    if company:
        conditions.append(col(JobPosting.company).ilike(f"%{company}%"))

    if company_ids:
        id_list = [int(i.strip()) for i in company_ids.split(",") if i.strip().isdigit()]
        if id_list:
            # Get company names for the IDs
            co_names = session.exec(
                select(Company.name).where(Company.id.in_(id_list))
            ).all()
            if co_names:
                conditions.append(col(JobPosting.company).in_(co_names))

    if priority:
        conditions.append(JobPosting.company_priority == priority)

    if role_category:
        conditions.append(col(JobPosting.role_category).ilike(f"%{role_category}%"))

    if experience_level:
        conditions.append(col(JobPosting.experience_level).ilike(f"%{experience_level}%"))

    if level_filter:
        levels = [lv.strip() for lv in level_filter.split(',') if lv.strip()]
        if levels:
            from sqlmodel import or_ as sql_or
            conditions.append(sql_or(*[col(JobPosting.experience_level) == lv for lv in levels]))

    if remote:
        conditions.append(col(JobPosting.remote_status).ilike(f"%{remote}%"))

    if min_score is not None:
        conditions.append(JobPosting.match_score >= min_score)

    # USA filter
    if usa_only:
        if include_unknown_location:
            # USA jobs OR unknown location (confidence 0)
            conditions.append(
                (JobPosting.is_usa == True) | (JobPosting.location_confidence == 0.0)
            )
        else:
            conditions.append(JobPosting.is_usa == True)

    # Senior filter (exclude by default)
    if not include_senior:
        conditions.append(JobPosting.is_senior == False)

    if state:
        conditions.append(col(JobPosting.state).ilike(f"%{state}%"))

    if new_since_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=new_since_hours)
        conditions.append(JobPosting.first_seen_at >= cutoff)

    if first_seen_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=first_seen_days)
        conditions.append(JobPosting.first_seen_at >= cutoff)

    if keyword:
        kw = f"%{keyword}%"
        conditions.append(
            col(JobPosting.job_title).ilike(kw)
            | col(JobPosting.matched_keywords).ilike(kw)
            | col(JobPosting.description_snippet).ilike(kw)
            | col(JobPosting.company).ilike(kw)
        )

    if skills:
        for skill in skills.split(","):
            s = skill.strip()
            if s:
                kw = f"%{s}%"
                conditions.append(
                    col(JobPosting.matched_keywords).ilike(kw)
                    | col(JobPosting.description_snippet).ilike(kw)
                )

    # View-based presets
    if view == "entry_level":
        conditions.append(JobPosting.is_senior == False)
        conditions.append(
            (JobPosting.is_entry_level == True) | (JobPosting.is_candidate_friendly == True)
        )
    elif view == "best":
        conditions.append(JobPosting.match_score >= 65)
    elif view == "all_usa":
        pass  # usa_only already applied above
    elif view == "adjacent":
        include_adjacent = True
        include_senior = True

    # Exclude software-only roles unless explicitly requested
    if not include_software:
        conditions.append(JobPosting.is_software_only == False)

    # Role flags filter: comma-separated list of flag names that must be True
    if role_flags:
        for flag_name in role_flags.split(","):
            flag_name = flag_name.strip()
            if flag_name and hasattr(JobPosting, flag_name):
                conditions.append(getattr(JobPosting, flag_name) == True)

    for cond in conditions:
        stmt = stmt.where(cond)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = session.exec(count_stmt).one()

    # Sort
    sort_col_map = {
        "match_score": JobPosting.match_score,
        "first_seen_at": JobPosting.first_seen_at,
        "last_seen_at": JobPosting.last_seen_at,
        "company": JobPosting.company,
        "job_title": JobPosting.job_title,
    }
    sort_col = sort_col_map.get(sort_by, JobPosting.match_score)
    if sort_order == "asc":
        stmt = stmt.order_by(col(sort_col).asc(), col(JobPosting.first_seen_at).desc())
    else:
        stmt = stmt.order_by(col(sort_col).desc(), col(JobPosting.first_seen_at).desc())

    # Paginate
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit)
    items = session.exec(stmt).all()

    return items, total_count


def _paginate(items: list, total: int, page: int, limit: int) -> dict[str, Any]:
    total_pages = max(1, (total + limit - 1) // limit)
    return {
        "items": items,
        "total_count": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


# ── Job endpoints ──────────────────────────────────────────────────────────────

@app.get("/jobs", response_model=PaginatedJobResponse)
def list_jobs(
    session: SessionDep,
    page: int = 1,
    limit: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = None,
    company: Optional[str] = None,
    company_ids: Optional[str] = None,
    priority: Optional[str] = None,
    role_category: Optional[str] = None,
    experience_level: Optional[str] = None,
    level_filter: Optional[str] = None,
    remote: Optional[str] = None,
    min_score: Optional[int] = None,
    new_since_hours: Optional[int] = None,
    first_seen_days: Optional[int] = None,
    keyword: Optional[str] = None,
    skills: Optional[str] = None,
    usa_only: bool = True,
    include_senior: bool = False,
    include_unknown_location: bool = True,
    include_software: bool = False,
    include_adjacent: bool = False,
    view: Optional[str] = None,
    role_flags: Optional[str] = None,
    state: Optional[str] = None,
    sort_by: str = "match_score",
    sort_order: str = "desc",
):
    items, total = _build_job_query(
        session, status=status, company=company, company_ids=company_ids,
        priority=priority, role_category=role_category, experience_level=experience_level,
        level_filter=level_filter,
        remote=remote, min_score=min_score, new_since_hours=new_since_hours,
        first_seen_days=first_seen_days, keyword=keyword, skills=skills,
        usa_only=usa_only, include_senior=include_senior,
        include_unknown_location=include_unknown_location,
        include_software=include_software, include_adjacent=include_adjacent,
        view=view, role_flags=role_flags,
        state=state, sort_by=sort_by, sort_order=sort_order, page=page, limit=limit,
    )
    return _paginate(items, total, page, limit)


@app.get("/jobs/new", response_model=PaginatedJobResponse)
def new_jobs(session: SessionDep, hours: int = 24, page: int = 1, limit: int = 50):
    items, total = _build_job_query(
        session, new_since_hours=hours, usa_only=False, include_senior=False,
        page=page, limit=limit,
    )
    return _paginate(items, total, page, limit)


@app.get("/jobs/best", response_model=PaginatedJobResponse)
def best_jobs(
    session: SessionDep,
    min_score: int = 65,
    page: int = 1,
    limit: int = Query(default=50, ge=1, le=200),
    keyword: Optional[str] = None,
    company: Optional[str] = None,
    priority: Optional[str] = None,
    role_category: Optional[str] = None,
    remote: Optional[str] = None,
    state: Optional[str] = None,
    new_since_hours: Optional[int] = None,
    usa_only: bool = True,
    include_senior: bool = False,
    include_software: bool = False,
):
    items, total = _build_job_query(
        session, min_score=min_score, usa_only=usa_only, include_senior=include_senior,
        include_software=include_software, keyword=keyword, company=company,
        priority=priority, role_category=role_category, remote=remote, state=state,
        new_since_hours=new_since_hours, sort_by="match_score", page=page, limit=limit,
    )
    return _paginate(items, total, page, limit)


@app.get("/jobs/entry-level", response_model=PaginatedJobResponse)
def entry_level_jobs(
    session: SessionDep,
    include_candidate_friendly: bool = True,
    page: int = 1,
    limit: int = Query(default=50, ge=1, le=200),
    # Full filter set — same as /jobs
    keyword: Optional[str] = None,
    company: Optional[str] = None,
    priority: Optional[str] = None,
    role_category: Optional[str] = None,
    remote: Optional[str] = None,
    min_score: Optional[int] = None,
    new_since_hours: Optional[int] = None,
    state: Optional[str] = None,
    usa_only: bool = True,
    include_senior: bool = False,
    include_software: bool = False,
):
    stmt = select(JobPosting).where(
        JobPosting.active_status == ActiveStatus.active,
        JobPosting.is_senior == False,
    )
    if include_candidate_friendly:
        stmt = stmt.where(
            (JobPosting.is_entry_level == True) | (JobPosting.is_candidate_friendly == True)
        )
    else:
        stmt = stmt.where(JobPosting.is_entry_level == True)

    if not include_software:
        stmt = stmt.where(JobPosting.is_software_only == False)

    # Apply optional filters
    if usa_only:
        stmt = stmt.where(
            (JobPosting.is_usa == True) | (JobPosting.location_confidence == 0.0)
        )
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            col(JobPosting.job_title).ilike(kw)
            | col(JobPosting.matched_keywords).ilike(kw)
            | col(JobPosting.description_snippet).ilike(kw)
            | col(JobPosting.company).ilike(kw)
        )
    if company:
        stmt = stmt.where(col(JobPosting.company).ilike(f"%{company}%"))
    if priority:
        stmt = stmt.where(JobPosting.company_priority == priority)
    if role_category:
        stmt = stmt.where(col(JobPosting.role_category).ilike(f"%{role_category}%"))
    if remote:
        stmt = stmt.where(col(JobPosting.remote_status).ilike(f"%{remote}%"))
    if min_score is not None:
        stmt = stmt.where(JobPosting.match_score >= min_score)
    if state:
        stmt = stmt.where(col(JobPosting.state).ilike(f"%{state}%"))
    if new_since_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=new_since_hours)
        stmt = stmt.where(JobPosting.first_seen_at >= cutoff)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.exec(count_stmt).one()
    stmt = stmt.order_by(col(JobPosting.match_score).desc(), col(JobPosting.first_seen_at).desc())
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    items = session.exec(stmt).all()
    return _paginate(items, total, page, limit)


@app.get("/jobs/removed", response_model=PaginatedJobResponse)
def removed_jobs(session: SessionDep, page: int = 1, limit: int = 50):
    items, total = _build_job_query(
        session, status="removed", usa_only=False, include_senior=True,
        sort_by="last_seen_at", page=page, limit=limit,
    )
    return _paginate(items, total, page, limit)


@app.get("/jobs/saved", response_model=PaginatedJobResponse)
def saved_jobs(session: SessionDep, page: int = 1, limit: int = 50):
    items, total = _build_job_query(
        session, status="saved", usa_only=False, include_senior=True,
        page=page, limit=limit,
    )
    return _paginate(items, total, page, limit)


@app.get("/jobs/applied", response_model=PaginatedJobResponse)
def applied_jobs(session: SessionDep, page: int = 1, limit: int = 50):
    items, total = _build_job_query(
        session, status="applied", usa_only=False, include_senior=True,
        sort_by="applied_at", page=page, limit=limit,
    )
    return _paginate(items, total, page, limit)


@app.get("/jobs/facets")
def job_facets(session: SessionDep, usa_only: bool = True, include_software: bool = False):
    """Return available filter facets with counts for the active job pool."""
    base_conds = [JobPosting.active_status == "active"]
    if usa_only:
        base_conds.append(
            (JobPosting.is_usa == True) | (JobPosting.location_confidence == 0.0)
        )
    if not include_software:
        base_conds.append(JobPosting.is_software_only == False)

    def facet_count(extra_conds):
        stmt = select(func.count(JobPosting.id)).where(*base_conds, *extra_conds)
        return session.exec(stmt).one() or 0

    role_cats = session.exec(
        select(JobPosting.role_category, func.count(JobPosting.id))
        .where(*base_conds)
        .group_by(JobPosting.role_category)
        .order_by(func.count(JobPosting.id).desc())
    ).all()

    priorities = session.exec(
        select(JobPosting.company_priority, func.count(JobPosting.id))
        .where(*base_conds)
        .group_by(JobPosting.company_priority)
        .order_by(JobPosting.company_priority)
    ).all()

    remote_statuses = session.exec(
        select(JobPosting.remote_status, func.count(JobPosting.id))
        .where(*base_conds)
        .group_by(JobPosting.remote_status)
        .order_by(func.count(JobPosting.id).desc())
    ).all()

    states_raw = session.exec(
        select(JobPosting.state, func.count(JobPosting.id))
        .where(*base_conds, JobPosting.state != "")
        .group_by(JobPosting.state)
        .order_by(func.count(JobPosting.id).desc())
        .limit(15)
    ).all()

    return {
        "role_categories": [{"value": r, "count": c} for r, c in role_cats if r],
        "priorities": [{"value": p, "count": c} for p, c in priorities if p],
        "remote_statuses": [{"value": r, "count": c} for r, c in remote_statuses if r],
        "states": [{"value": s, "count": c} for s, c in states_raw],
        "entry_level_count": facet_count([
            (JobPosting.is_entry_level == True) | (JobPosting.is_candidate_friendly == True)
        ]),
        "candidate_friendly_count": facet_count([JobPosting.is_candidate_friendly == True]),
        "senior_count": facet_count([JobPosting.is_senior == True]),
        "remote_count": facet_count([col(JobPosting.remote_status).ilike("%remote%")]),
        "new_24h_count": facet_count([
            JobPosting.first_seen_at >= datetime.now(timezone.utc) - timedelta(hours=24)
        ]),
    }


@app.get("/jobs/search-suggestions")
def search_suggestions(q: str, session: SessionDep, limit: int = 8):
    """Return autocomplete suggestions for job titles and companies."""
    if not q or len(q) < 2:
        return {"suggestions": []}
    pattern = f"%{q}%"
    titles = session.exec(
        select(JobPosting.normalized_title)
        .where(
            col(JobPosting.normalized_title).ilike(pattern),
            JobPosting.active_status == "active",
        )
        .distinct()
        .limit(limit)
    ).all()
    companies = session.exec(
        select(JobPosting.company)
        .where(
            col(JobPosting.company).ilike(pattern),
            JobPosting.active_status == "active",
        )
        .distinct()
        .limit(4)
    ).all()
    return {
        "suggestions": list(dict.fromkeys([t for t in titles if t] + [c for c in companies if c]))[:limit]
    }


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int, session: SessionDep):
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.patch("/jobs/{job_id}/status")
def update_job_status(job_id: int, update: StatusUpdate, session: SessionDep):
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    now = datetime.now(timezone.utc)
    if update.active_status:
        if update.active_status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        job.active_status = update.active_status
        if update.active_status == "saved" and not job.saved_at:
            job.saved_at = now
        elif update.active_status == "applied" and not job.applied_at:
            job.applied_at = now
        elif update.active_status == "ignored" and not job.ignored_at:
            job.ignored_at = now

    if update.application_status is not None:
        job.application_status = update.application_status
    if update.notes is not None:
        job.notes = update.notes
    if update.resume_version_used is not None:
        job.resume_version_used = update.resume_version_used

    session.add(job)
    session.commit()
    return {"ok": True}


# Keep old POST endpoint for backward compat
@app.post("/jobs/{job_id}/status")
def update_job_status_post(job_id: int, update: StatusUpdate, session: SessionDep):
    return update_job_status(job_id, update, session)


@app.patch("/jobs/{job_id}/notes")
def update_notes(job_id: int, notes: str, session: SessionDep):
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.notes = notes
    session.add(job)
    session.commit()
    return {"ok": True}


# ── Company endpoints ──────────────────────────────────────────────────────────

def _build_company_response(company: Company, session: Session) -> dict:
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    total = session.exec(
        select(func.count(JobPosting.id)).where(
            JobPosting.company == company.name,
            JobPosting.active_status == ActiveStatus.active,
        )
    ).one() or 0

    usa = session.exec(
        select(func.count(JobPosting.id)).where(
            JobPosting.company == company.name,
            JobPosting.active_status == ActiveStatus.active,
            JobPosting.is_usa == True,
        )
    ).one() or 0

    entry = session.exec(
        select(func.count(JobPosting.id)).where(
            JobPosting.company == company.name,
            JobPosting.active_status == ActiveStatus.active,
            (JobPosting.is_entry_level == True) | (JobPosting.is_candidate_friendly == True),
        )
    ).one() or 0

    relevant = session.exec(
        select(func.count(JobPosting.id)).where(
            JobPosting.company == company.name,
            JobPosting.active_status == ActiveStatus.active,
            JobPosting.is_usa == True,
            JobPosting.is_software_only == False,
            JobPosting.is_senior == False,
        )
    ).one() or 0

    # viewable = what the default /jobs filter actually shows (USA OR unknown-loc, non-senior, non-software)
    viewable = session.exec(
        select(func.count(JobPosting.id)).where(
            JobPosting.company == company.name,
            JobPosting.active_status == ActiveStatus.active,
            (JobPosting.is_usa == True) | (JobPosting.location_confidence == 0.0),
            JobPosting.is_software_only == False,
            JobPosting.is_senior == False,
        )
    ).one() or 0

    new_today = session.exec(
        select(func.count(JobPosting.id)).where(
            JobPosting.company == company.name,
            JobPosting.active_status == ActiveStatus.active,
            JobPosting.first_seen_at >= cutoff_24h,
        )
    ).one() or 0

    # Scrape status
    if company.scrape_error_count > 3:
        scrape_status = "failed"
    elif company.scrape_error_count > 0:
        scrape_status = "warning"
    elif company.last_scraped_at:
        scrape_status = "healthy"
    else:
        scrape_status = "never"

    return {
        "id": company.id,
        "name": company.name,
        "category": company.category,
        "priority": company.priority,
        "careers_url": company.careers_url,
        "company_search_url": getattr(company, "company_search_url", "") or "",
        "ats_platform": company.ats_platform,
        "enabled": company.enabled,
        "last_scraped_at": company.last_scraped_at,
        "scrape_error_count": company.scrape_error_count,
        "total_active_jobs": total,
        "relevant_active_jobs": relevant,
        "viewable_jobs": viewable,
        "usa_active_jobs": usa,
        "entry_level_jobs": entry,
        "new_jobs_today": new_today,
        "scrape_status": scrape_status,
    }


@app.get("/companies")
def list_companies(session: SessionDep, with_counts: bool = True):
    companies = session.exec(select(Company).order_by(Company.priority, Company.name)).all()
    if with_counts:
        return [_build_company_response(c, session) for c in companies]
    return [{"id": c.id, "name": c.name, "category": c.category, "priority": c.priority,
             "careers_url": c.careers_url, "ats_platform": c.ats_platform,
             "enabled": c.enabled, "last_scraped_at": c.last_scraped_at} for c in companies]


@app.get("/companies/{company_id}")
def get_company(company_id: int, session: SessionDep):
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return _build_company_response(company, session)


@app.get("/companies/{company_id}/jobs", response_model=PaginatedJobResponse)
def company_jobs(
    company_id: int,
    session: SessionDep,
    page: int = 1,
    limit: int = 50,
    usa_only: bool = False,
    include_senior: bool = True,
):
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    items, total = _build_job_query(
        session, company=company.name, usa_only=usa_only,
        include_senior=include_senior, page=page, limit=limit,
    )
    return _paginate(items, total, page, limit)


# ── Scrape endpoints ────────────────────────────────────────────────────────────

@app.get("/scrape-runs", response_model=list[ScrapeRunResponse])
def list_scrape_runs(session: SessionDep, limit: int = 20):
    stmt = select(ScrapeRun).order_by(col(ScrapeRun.started_at).desc()).limit(limit)
    return session.exec(stmt).all()


@app.post("/scrape/run-now")
async def trigger_scrape(background_tasks: BackgroundTasks):
    async def _run():
        from .scrape_engine import run_scrape
        await run_scrape(triggered_by="manual")
    background_tasks.add_task(_run)
    return {"message": "Scrape started", "triggered_by": "manual"}


@app.get("/scrape-errors")
def scrape_errors(session: SessionDep, limit: int = 50):
    stmt = select(ScrapeError).order_by(col(ScrapeError.occurred_at).desc()).limit(limit)
    return session.exec(stmt).all()


@app.get("/scrape-health")
def scrape_health(session: SessionDep):
    runs = session.exec(
        select(ScrapeRun).order_by(col(ScrapeRun.started_at).desc()).limit(10)
    ).all()
    recent_errors = session.exec(
        select(ScrapeError).order_by(col(ScrapeError.occurred_at).desc()).limit(20)
    ).all()
    companies = session.exec(select(Company)).all()
    company_data = [_build_company_response(c, session) for c in companies]

    return {
        "recent_runs": [
            {
                "id": r.id, "started_at": r.started_at, "finished_at": r.finished_at,
                "companies_scraped": r.companies_scraped, "jobs_found": r.jobs_found,
                "new_jobs": r.new_jobs, "removed_jobs": r.removed_jobs,
                "errors": r.errors, "triggered_by": r.triggered_by,
            }
            for r in runs
        ],
        "recent_errors": [
            {"company": e.company, "error_message": e.error_message, "occurred_at": e.occurred_at}
            for e in recent_errors
        ],
        "companies": company_data,
    }


# ── Stats / Analytics ──────────────────────────────────────────────────────────

@app.get("/analytics/summary")
def analytics_summary(session: SessionDep):
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    def count(q):
        return session.exec(select(func.count(JobPosting.id)).where(*q)).one() or 0

    def co_count(q):
        return session.exec(select(func.count(Company.id)).where(*q)).one() or 0

    total_active = count([JobPosting.active_status == ActiveStatus.active])
    new_24h = count([JobPosting.active_status == ActiveStatus.active, JobPosting.first_seen_at >= cutoff_24h])
    entry_level = count([
        JobPosting.active_status == ActiveStatus.active,
        (JobPosting.is_entry_level == True) | (JobPosting.is_candidate_friendly == True),
        JobPosting.is_senior == False,
    ])
    # Honest split: explicitly entry-level vs. inferred "likely junior"
    strict_entry = count([
        JobPosting.active_status == ActiveStatus.active,
        JobPosting.is_entry_level == True,
        JobPosting.is_senior == False,
    ])
    candidate_friendly = count([
        JobPosting.active_status == ActiveStatus.active,
        JobPosting.is_candidate_friendly == True,
        JobPosting.is_entry_level == False,
        JobPosting.is_senior == False,
    ])
    usa_count = count([JobPosting.active_status == ActiveStatus.active, JobPosting.is_usa == True])
    remote_count = count([
        JobPosting.active_status == ActiveStatus.active,
        col(JobPosting.remote_status).in_(["Remote", "remote"]),
    ])
    high_score = count([JobPosting.active_status == ActiveStatus.active, JobPosting.match_score >= 70])
    saved = count([JobPosting.active_status == ActiveStatus.saved])
    applied = count([JobPosting.active_status == ActiveStatus.applied])
    total_companies = co_count([Company.enabled == True])

    last_run = session.exec(
        select(ScrapeRun).order_by(col(ScrapeRun.started_at).desc()).limit(1)
    ).first()

    return {
        "total_active": total_active,
        "new_24h": new_24h,
        "entry_level_count": entry_level,
        "strict_entry_count": strict_entry,
        "candidate_friendly_count": candidate_friendly,
        "usa_count": usa_count,
        "remote_count": remote_count,
        "high_score_count": high_score,
        "saved_count": saved,
        "applied_count": applied,
        "total_companies": total_companies,
        "last_run": {
            "id": last_run.id,
            "started_at": last_run.started_at,
            "finished_at": last_run.finished_at,
            "companies_scraped": last_run.companies_scraped,
            "jobs_found": last_run.jobs_found,
            "new_jobs": last_run.new_jobs,
            "removed_jobs": last_run.removed_jobs,
            "errors": last_run.errors,
            "triggered_by": last_run.triggered_by,
        } if last_run else None,
    }


@app.get("/stats")
def stats(session: SessionDep):
    return analytics_summary(session)


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
