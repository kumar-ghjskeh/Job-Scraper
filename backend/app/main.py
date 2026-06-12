"""FastAPI application — RTL/DV Job Radar API."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, col, func, select

from .config import settings
from .database import get_session, init_db
from .models import ActiveStatus, Company, JobPosting, ResumeProfile, ScrapeError, ScrapeRun, Watchlist
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
    from .config import load_all_companies
    from .database import engine
    # Seed the directory with EVERY company (enabled + disabled "Direct search"),
    # so the Companies page always lists them all and keeps their config in sync.
    with Session(engine) as session:
        for cfg in load_all_companies():
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
                # Keep mutable config fields in sync with the YAML.
                existing.category = cfg.get("category", existing.category)
                existing.priority = cfg.get("priority", existing.priority)
                existing.careers_url = cfg.get("careers_url", existing.careers_url)
                existing.company_search_url = cfg.get("company_search_url", getattr(existing, "company_search_url", ""))
                existing.ats_platform = cfg.get("ats_platform", existing.ats_platform)
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
    new_grad_fit: int = 0
    experienced_fit: int = 0
    new_grad_fit_label: str = ""
    overall_recommendation: str = ""
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
    follow_up_date: str = ""
    confirmation_id: str = ""
    recruiter_contact: str = ""
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
    follow_up_date: Optional[str] = None
    confirmation_id: Optional[str] = None
    recruiter_contact: Optional[str] = None


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
    posted_within_hours: Optional[int] = None,
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
    h1b_only: bool = False,
    sort_by: str = "new_grad_fit",
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
        # Selecting a senior tier must lift the default senior gate below, or the
        # filter and the gate contradict and return zero results.
        if any(lv in ("Senior", "Staff", "Principal", "Lead", "Manager", "Director")
               for lv in levels):
            include_senior = True
        if levels:
            from sqlmodel import and_ as sql_and, or_ as sql_or
            # The seniority classifier only ever emits New Grad / Junior / Mid-Level /
            # Senior / Staff / Principal / Lead / Manager (no "Entry Level"/"Associate"),
            # so a plain label match leaves the early-career chips empty. Map the
            # early-career chips onto the real entry/candidate-friendly signals.
            level_conds = []
            for lv in levels:
                if lv == "New Grad":
                    level_conds.append(col(JobPosting.experience_level) == "New Grad")
                    level_conds.append(JobPosting.is_entry_level == True)  # noqa: E712
                elif lv == "Entry Level":
                    level_conds.append(col(JobPosting.experience_level).in_(["Entry Level", "New Grad"]))
                    level_conds.append(JobPosting.is_entry_level == True)  # noqa: E712
                elif lv in ("Junior", "Associate"):
                    level_conds.append(col(JobPosting.experience_level) == lv)
                    level_conds.append(sql_and(
                        JobPosting.is_candidate_friendly == True,  # noqa: E712
                        JobPosting.is_senior == False,             # noqa: E712
                        JobPosting.is_entry_level == False,        # noqa: E712
                    ))
                else:
                    level_conds.append(col(JobPosting.experience_level) == lv)
            conditions.append(sql_or(*level_conds))

    if remote:
        conditions.append(col(JobPosting.remote_status).ilike(f"%{remote}%"))

    if min_score is not None:
        # "Min score" filter is re-based on New Grad Fit — for this candidate,
        # "high score" means "realistic for a new grad", not intrinsic relevance.
        conditions.append(JobPosting.new_grad_fit >= min_score)

    # USA filter
    if usa_only:
        if include_unknown_location:
            # USA jobs OR unknown location (confidence 0)
            conditions.append(
                (JobPosting.is_usa == True) | (JobPosting.location_confidence == 0.0)
            )
        else:
            conditions.append(JobPosting.is_usa == True)

    # Senior filter (exclude by default) — but an explicit keyword search should
    # surface ALL matching roles (e.g. searching a company name shows its senior
    # roles too), so the senior gate is lifted whenever a keyword is present.
    if not include_senior and not keyword:
        conditions.append(JobPosting.is_senior == False)

    if state:
        conditions.append(col(JobPosting.state).ilike(f"%{state}%"))

    if new_since_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=new_since_hours)
        conditions.append(JobPosting.first_seen_at >= cutoff)

    if first_seen_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=first_seen_days)
        conditions.append(JobPosting.first_seen_at >= cutoff)

    # "Posted within" filters on the company's actual POSTED date (what the card
    # shows), NOT when we scraped it. A job with no known posted date is excluded
    # from short windows — we can't claim it was posted that recently.
    if posted_within_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=posted_within_hours)
        conditions.append(col(JobPosting.posted_date).is_not(None))
        conditions.append(JobPosting.posted_date >= cutoff)

    if keyword:
        # Accurate multi-token search (portable SQLite + Postgres). Each token must
        # appear in at least one field (AND of tokens, OR of fields). High-signal
        # fields (company/title/skills/role/location) match as substrings; the free
        # text description matches on WHOLE WORDS only — so e.g. "intel" returns
        # Intel, not every job whose description says "intelligence".
        from sqlalchemy import literal
        from sqlmodel import or_ as sql_or
        substr_fields = [
            JobPosting.job_title, JobPosting.normalized_title, JobPosting.company,
            JobPosting.matched_keywords, JobPosting.role_category,
            JobPosting.experience_level, JobPosting.state, JobPosting.location,
            JobPosting.ats_platform,
        ]
        word_fields = [JobPosting.cleaned_description, JobPosting.description_snippet]
        for tok in keyword.split():
            tok = tok.strip()
            if not tok:
                continue
            kw = f"%{tok}%"
            ors = [col(f).ilike(kw) for f in substr_fields]
            # Word-boundary on description: pad with spaces and require " token ".
            word = f"% {tok} %"
            ors += [
                (literal(" ").concat(col(f)).concat(literal(" "))).ilike(word)
                for f in word_fields
            ]
            conditions.append(sql_or(*ors))

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
        conditions.append(JobPosting.new_grad_fit >= 65)
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

    # H1B sponsor-friendly: restrict to companies known to sponsor (sponsors_h1b is
    # a company-level signal, not a column, so filter by the known-sponsor name set).
    if h1b_only:
        from .eligibility import _KNOWN_SPONSOR
        conditions.append(func.lower(col(JobPosting.company)).in_(list(_KNOWN_SPONSOR)))

    for cond in conditions:
        stmt = stmt.where(cond)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = session.exec(count_stmt).one()

    # Sort — default ranks by New Grad Fit (primary score for this candidate),
    # with role relevance and recency as natural tiebreakers.
    sort_col_map = {
        "new_grad_fit": JobPosting.new_grad_fit,
        "match_score": JobPosting.match_score,
        "experienced_fit": JobPosting.experienced_fit,
        "first_seen_at": JobPosting.first_seen_at,
        "last_seen_at": JobPosting.last_seen_at,
        "posted_date": JobPosting.posted_date,
        "company": JobPosting.company,
        "job_title": JobPosting.job_title,
    }
    sort_col = sort_col_map.get(sort_by, JobPosting.new_grad_fit)
    if sort_order == "asc":
        stmt = stmt.order_by(col(sort_col).asc(), col(JobPosting.match_score).desc(), col(JobPosting.first_seen_at).desc())
    else:
        stmt = stmt.order_by(col(sort_col).desc(), col(JobPosting.match_score).desc(), col(JobPosting.first_seen_at).desc())

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
    posted_within_hours: Optional[int] = None,
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
    h1b_only: bool = False,
    sort_by: str = "new_grad_fit",
    sort_order: str = "desc",
):
    items, total = _build_job_query(
        session, status=status, company=company, company_ids=company_ids,
        priority=priority, role_category=role_category, experience_level=experience_level,
        level_filter=level_filter,
        remote=remote, min_score=min_score, new_since_hours=new_since_hours,
        first_seen_days=first_seen_days, posted_within_hours=posted_within_hours,
        keyword=keyword, skills=skills,
        usa_only=usa_only, include_senior=include_senior,
        include_unknown_location=include_unknown_location,
        include_software=include_software, include_adjacent=include_adjacent,
        view=view, role_flags=role_flags,
        state=state, h1b_only=h1b_only, sort_by=sort_by, sort_order=sort_order, page=page, limit=limit,
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


# ── Resume intelligence (Phase 3) ────────────────────────────────────────────

def _active_resume(session: Session) -> Optional[ResumeProfile]:
    """The resume version marked active, else the most recent one."""
    rp = session.exec(
        select(ResumeProfile).where(ResumeProfile.is_active == True)  # noqa: E712
        .order_by(col(ResumeProfile.id).desc())
    ).first()
    if rp:
        return rp
    return session.exec(select(ResumeProfile).order_by(col(ResumeProfile.id).desc())).first()


def _current_profile(session: Session, resume_id: Optional[int] = None) -> Optional[dict]:
    """Parsed profile for a specific resume id, else the active resume."""
    rp = session.get(ResumeProfile, resume_id) if resume_id else _active_resume(session)
    if not rp or not rp.profile_json:
        return None
    try:
        return json.loads(rp.profile_json)
    except Exception:
        return None


def _job_match_input(job: JobPosting) -> dict:
    now = datetime.now(timezone.utc)
    fs = job.first_seen_at
    is_fresh = False
    if fs:
        if fs.tzinfo is None:
            fs = fs.replace(tzinfo=timezone.utc)
        is_fresh = (now - fs) < timedelta(hours=24)
    return {
        "job_title": job.job_title, "cleaned_description": job.cleaned_description,
        "matched_keywords": job.matched_keywords, "role_category": job.role_category,
        "match_score": job.match_score, "is_candidate_friendly": job.is_candidate_friendly,
        "eligibility_risk": job.eligibility_risk, "sponsors_h1b": job.sponsors_h1b,
        "is_fresh": is_fresh,
        # Seniority context + stored job-intrinsic fit scores
        "experience_level": job.experience_level, "is_senior": job.is_senior,
        "is_entry_level": job.is_entry_level, "years_required_min": job.years_required_min,
        "new_grad_fit": job.new_grad_fit, "experienced_fit": job.experienced_fit,
    }


def _resume_brief(rp: ResumeProfile) -> dict:
    try:
        prof = json.loads(rp.profile_json) if rp.profile_json else {}
    except Exception:
        prof = {}
    return {
        "id": rp.id,
        "label": rp.label or (prof.get("role_focus") or rp.filename or f"Resume {rp.id}"),
        "filename": rp.filename,
        "is_active": rp.is_active,
        "uploaded_at": rp.uploaded_at,
        "role_focus": prof.get("role_focus", ""),
        "skill_count": len(prof.get("all_skills", []) or []),
    }


@app.post("/resume/upload")
async def upload_resume(session: SessionDep, file: UploadFile = File(...), label: str = Form(default="")):
    from .resume_parser import parse_resume
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Resume too large (max 8 MB)")
    try:
        profile = parse_resume(data, file.filename or "resume.txt")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse resume: {e}")
    # New upload becomes the active version; demote the others (keep them).
    for other in session.exec(select(ResumeProfile)).all():
        if other.is_active:
            other.is_active = False
            session.add(other)
    prof_dict = profile.to_dict()
    rp = ResumeProfile(
        filename=file.filename or "",
        label=(label or "").strip() or prof_dict.get("role_focus", "") or (file.filename or ""),
        is_active=True,
        profile_json=json.dumps(prof_dict),
    )
    session.add(rp)
    session.commit()
    session.refresh(rp)
    return {"ok": True, "id": rp.id, "profile": prof_dict, "filename": file.filename, "label": rp.label}


@app.get("/resumes")
def list_resumes(session: SessionDep):
    rows = session.exec(select(ResumeProfile).order_by(col(ResumeProfile.id).desc())).all()
    return [_resume_brief(r) for r in rows]


@app.get("/resume")
def get_resume(session: SessionDep):
    rp = _active_resume(session)
    if not rp or not rp.profile_json:
        return {"profile": None}
    return {"profile": json.loads(rp.profile_json), "filename": rp.filename,
            "uploaded_at": rp.uploaded_at, "id": rp.id, "label": rp.label}


@app.post("/resume/{resume_id}/activate")
def activate_resume(resume_id: int, session: SessionDep):
    target = session.get(ResumeProfile, resume_id)
    if not target:
        raise HTTPException(status_code=404, detail="Resume not found")
    for r in session.exec(select(ResumeProfile)).all():
        r.is_active = (r.id == resume_id)
        session.add(r)
    session.commit()
    return {"ok": True, "active_id": resume_id}


@app.delete("/resume/{resume_id}")
def delete_resume_one(resume_id: int, session: SessionDep):
    rp = session.get(ResumeProfile, resume_id)
    if rp:
        was_active = rp.is_active
        session.delete(rp)
        session.commit()
        if was_active:
            nxt = session.exec(select(ResumeProfile).order_by(col(ResumeProfile.id).desc())).first()
            if nxt:
                nxt.is_active = True
                session.add(nxt)
                session.commit()
    return {"ok": True}


@app.delete("/resume")
def delete_resume(session: SessionDep):
    """Delete all resume versions (legacy 'remove resume' action)."""
    for old in session.exec(select(ResumeProfile)).all():
        session.delete(old)
    session.commit()
    return {"ok": True}


@app.get("/jobs/resume-matches")
def resume_matches(session: SessionDep, page: int = 1, limit: int = Query(default=50, ge=1, le=200),
                   include_senior: bool = False, resume_id: Optional[int] = None, sort: str = "match"):
    profile = _current_profile(session, resume_id)
    if not profile:
        return {"items": [], "total_count": 0, "page": 1, "limit": limit,
                "total_pages": 1, "has_next": False, "has_prev": False, "no_resume": True}
    from .resume_match import compute_match
    conds = [JobPosting.active_status == "active",
             (JobPosting.is_usa == True) | (JobPosting.location_confidence == 0.0),
             JobPosting.is_software_only == False]
    if not include_senior:
        conds.append(JobPosting.is_senior == False)
    jobs = session.exec(select(JobPosting).where(*conds)).all()
    scored = []
    for job in jobs:
        m = compute_match(profile, _job_match_input(job))
        item = JobResponse.model_validate(job).model_dump()
        item["resume_match"] = m["resume_match"]
        item["new_grad_fit"] = m["new_grad_fit"]
        item["experienced_fit"] = m["experienced_fit"]
        item["overall_recommendation"] = m["overall_recommendation"]
        item["match_breakdown"] = m["match_breakdown"]
        item["defensibility"] = m["defensibility"]
        item["apply_priority"] = m["apply_priority"]
        item["matched_skills"] = m["matched_skills"][:6]
        item["missing_skills"] = m["missing_skills"][:6]
        scored.append(item)
    bd = lambda it, k: (it.get("match_breakdown") or {}).get(k, 0)  # noqa: E731
    # Three recruiter-grade sorts only: overall fit, how realistic the level is
    # for this candidate, and freshness. Each breaks ties on the other signal so
    # the orderings are genuinely distinct.
    sort_keys = {
        "match": lambda it: (it["resume_match"], bd(it, "experience"), it["match_score"]),
        "experience": lambda it: (bd(it, "experience"), it["resume_match"]),
        "newest": lambda it: (str(it.get("posted_date") or it.get("first_seen_at") or ""), it["resume_match"]),
    }
    # Back-compat: fold the retired skills/projects options into best-match.
    scored.sort(key=sort_keys.get(sort, sort_keys["match"]), reverse=True)
    total = len(scored)
    start = (page - 1) * limit
    page_items = scored[start:start + limit]
    total_pages = max(1, (total + limit - 1) // limit)
    return {"items": page_items, "total_count": total, "page": page, "limit": limit,
            "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1}


@app.post("/jobs/match-batch")
def job_match_batch(payload: dict, session: SessionDep):
    profile = _current_profile(session)
    if not profile:
        return {"matches": {}}
    from .resume_match import compute_match
    ids = (payload.get("ids") or [])[:120]
    out: dict[str, Any] = {}
    for jid in ids:
        job = session.get(JobPosting, jid)
        if job:
            m = compute_match(profile, _job_match_input(job))
            out[str(jid)] = {"resume_match": m["resume_match"], "apply_priority": m["apply_priority"]}
    return {"matches": out}


@app.get("/resume/skill-gaps")
def skill_gaps(session: SessionDep, min_match: int = 45):
    profile = _current_profile(session)
    if not profile:
        return {"gaps": [], "high_match_jobs": 0, "no_resume": True}
    from collections import Counter
    from .resume_match import compute_match
    conds = [JobPosting.active_status == "active",
             (JobPosting.is_usa == True) | (JobPosting.location_confidence == 0.0),
             JobPosting.is_software_only == False, JobPosting.is_senior == False]
    jobs = session.exec(select(JobPosting).where(*conds)).all()
    counter: Counter = Counter()
    n_high = 0
    for job in jobs:
        m = compute_match(profile, _job_match_input(job))
        if m["resume_match"] >= min_match:
            n_high += 1
            for sk in m["missing_skills"]:
                counter[sk] += 1
    gaps = [{"skill": s, "count": n} for s, n in counter.most_common(15)]
    return {"gaps": gaps, "high_match_jobs": n_high}


@app.get("/jobs/{job_id}/match")
def job_match(job_id: int, session: SessionDep, resume_id: Optional[int] = None):
    profile = _current_profile(session, resume_id)
    if not profile:
        raise HTTPException(status_code=404, detail="No resume uploaded")
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    from .resume_match import compute_match
    return compute_match(profile, _job_match_input(job))


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
        # Pipeline stage implies the job belongs in the Applied workspace.
        if update.application_status in ("Applied", "Assessment", "Interview", "Offer") and not job.applied_at:
            job.applied_at = now
            if job.active_status not in ("applied",):
                job.active_status = ActiveStatus.applied
    if update.notes is not None:
        job.notes = update.notes
    if update.resume_version_used is not None:
        job.resume_version_used = update.resume_version_used
    if update.follow_up_date is not None:
        job.follow_up_date = update.follow_up_date
    if update.confirmation_id is not None:
        job.confirmation_id = update.confirmation_id
    if update.recruiter_contact is not None:
        job.recruiter_contact = update.recruiter_contact

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

    # viewable = EXACTLY what clicking "View Jobs" shows in the All Jobs list, so
    # the count on the card always equals the number of jobs the user then sees.
    # The All Jobs default is usa_only + include_unknown_location + non-software,
    # with senior roles INCLUDED (include_senior defaults true), so mirror that
    # here — otherwise the card under-counts and the totals never reconcile.
    viewable = session.exec(
        select(func.count(JobPosting.id)).where(
            JobPosting.company == company.name,
            JobPosting.active_status == ActiveStatus.active,
            (JobPosting.is_usa == True) | (JobPosting.location_confidence == 0.0),
            JobPosting.is_software_only == False,
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

    # Parser confidence — how complete/trustworthy the parsed records are for this
    # company, derived from the average per-job data-quality score (0–100) across its
    # active postings. A low value flags a parser that is extracting thin/garbled data
    # even when the scrape itself "succeeds".
    avg_quality = session.exec(
        select(func.avg(JobPosting.data_quality_score)).where(
            JobPosting.company == company.name,
            JobPosting.active_status == ActiveStatus.active,
        )
    ).one()
    parser_confidence = int(round(avg_quality)) if avg_quality else 0

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
        "parser_confidence": parser_confidence,
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

    # All browseable cards count the SAME USA-relevant pool the All Jobs list
    # shows (USA or unknown-location, non-software), so "Verified Active" always
    # equals the list count and the cards reconcile. USA is a hard gate here.
    USA_VIEW = [
        (JobPosting.is_usa == True) | (JobPosting.location_confidence == 0.0),
        JobPosting.is_software_only == False,
    ]
    active = [JobPosting.active_status == ActiveStatus.active]

    total_active = count(active + USA_VIEW)
    new_24h = count(active + USA_VIEW + [JobPosting.first_seen_at >= cutoff_24h])
    entry_level = count(active + USA_VIEW + [
        (JobPosting.is_entry_level == True) | (JobPosting.is_candidate_friendly == True),
        JobPosting.is_senior == False,
    ])
    # Honest split: explicitly entry-level vs. inferred "likely junior"
    strict_entry = count(active + USA_VIEW + [
        JobPosting.is_entry_level == True, JobPosting.is_senior == False,
    ])
    candidate_friendly = count(active + USA_VIEW + [
        JobPosting.is_candidate_friendly == True,
        JobPosting.is_entry_level == False, JobPosting.is_senior == False,
    ])
    usa_count = count(active + [JobPosting.is_usa == True])
    remote_count = count(active + USA_VIEW + [
        col(JobPosting.remote_status).in_(["Remote", "remote"]),
    ])
    # "High priority" + a dedicated new-grad card are both re-based on New Grad Fit.
    high_score = count(active + USA_VIEW + [JobPosting.new_grad_fit >= 70])
    strong_new_grad = count(active + USA_VIEW + [JobPosting.new_grad_fit >= 75])
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
        "strong_new_grad_count": strong_new_grad,
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


# ── Watchlists / saved searches (Phase 4) ────────────────────────────────────

class WatchlistCreate(BaseModel):
    name: str
    filters: dict = {}
    alert_enabled: bool = True


_WL_FILTER_KEYS = {
    "keyword", "role_category", "level_filter", "state", "priority", "remote",
    "min_score", "company", "usa_only", "include_senior", "role_flags",
}


def _wl_counts(session: Session, filters: dict, since: datetime) -> tuple[int, int]:
    f = {k: v for k, v in (filters or {}).items() if k in _WL_FILTER_KEYS and v not in (None, "", [])}
    _, total = _build_job_query(session, page=1, limit=1, **f)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    hours = max(1, int((datetime.now(timezone.utc) - since).total_seconds() // 3600) + 1)
    _, new = _build_job_query(session, page=1, limit=1, new_since_hours=hours, **f)
    return total, new


@app.get("/watchlists")
def list_watchlists(session: SessionDep):
    wls = session.exec(select(Watchlist).order_by(col(Watchlist.created_at).desc())).all()
    out = []
    for w in wls:
        try:
            filters = json.loads(w.filters_json) if w.filters_json else {}
        except Exception:
            filters = {}
        total, new = _wl_counts(session, filters, w.last_checked_at)
        out.append({
            "id": w.id, "name": w.name, "filters": filters, "alert_enabled": w.alert_enabled,
            "last_checked_at": w.last_checked_at, "total": total, "new_count": new,
        })
    return out


@app.post("/watchlists")
def create_watchlist(payload: WatchlistCreate, session: SessionDep):
    w = Watchlist(name=payload.name, filters_json=json.dumps(payload.filters or {}), alert_enabled=payload.alert_enabled)
    session.add(w); session.commit(); session.refresh(w)
    return {"ok": True, "id": w.id}


@app.delete("/watchlists/{wl_id}")
def delete_watchlist(wl_id: int, session: SessionDep):
    w = session.get(Watchlist, wl_id)
    if w:
        session.delete(w); session.commit()
    return {"ok": True}


@app.post("/watchlists/{wl_id}/check")
def check_watchlist(wl_id: int, session: SessionDep):
    w = session.get(Watchlist, wl_id)
    if not w:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    w.last_checked_at = datetime.now(timezone.utc)
    session.add(w); session.commit()
    return {"ok": True}


# ── Email digest (Phase 4) ───────────────────────────────────────────────────

@app.get("/digest/preview")
def digest_preview(session: SessionDep):
    from .services.digest import build_digest
    return build_digest(session)


@app.post("/digest/send")
async def digest_send(session: SessionDep):
    from .services.digest import build_digest, send_digest_email
    data = build_digest(session)
    ok = await send_digest_email(data)
    return {"sent": ok, "configured": ok is not None, **data}


@app.get("/export/applications.csv")
def export_applications(session: SessionDep):
    """Export every saved / applied / pipeline-tracked job as CSV for offline tracking."""
    import csv
    import io
    from fastapi import Response

    jobs = session.exec(
        select(JobPosting).where(
            (JobPosting.active_status.in_(["saved", "applied"]))  # type: ignore[attr-defined]
            | (col(JobPosting.application_status) != "")
        ).order_by(col(JobPosting.applied_at).desc(), col(JobPosting.saved_at).desc())
    ).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Company", "Title", "Location", "Stage", "Status", "Relevance",
        "Resume Used", "Applied On", "Follow-up", "Confirmation ID",
        "Recruiter", "Apply URL", "Notes",
    ])
    for j in jobs:
        w.writerow([
            j.company, j.job_title, j.location, j.application_status or "", j.active_status,
            j.match_score, j.resume_version_used or "",
            j.applied_at.date().isoformat() if j.applied_at else "",
            j.follow_up_date or "", j.confirmation_id or "", j.recruiter_contact or "",
            j.safe_apply_url or j.apply_url, (j.notes or "").replace("\n", " "),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ashborne-applications.csv"},
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": "5.0.0"}
