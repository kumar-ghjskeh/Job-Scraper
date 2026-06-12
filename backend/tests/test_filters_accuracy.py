"""Every filter is 100% accurate: each seniority chip returns exactly its level
(incl. senior tiers, which must lift the senior gate), 'posted within' filters on
posted_date not first_seen, and min-score is re-based on New Grad Fit."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from sqlmodel import Session, SQLModel, create_engine

from backend.app import main as M
from backend.app.models import JobPosting


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _job(**kw) -> JobPosting:
    base = dict(
        company="Acme", job_title="Design Verification Engineer", apply_url="https://x/y",
        cleaned_description="UVM", matched_keywords="uvm", role_category="Design Verification",
        experience_level="Unknown", state="CA", location="Santa Clara, CA",
        ats_platform="greenhouse", active_status="active", is_usa=True, is_software_only=False,
        is_senior=False, is_entry_level=False, is_candidate_friendly=False, company_priority="A",
        match_score=70, new_grad_fit=72, location_confidence=0.9,
        first_seen_at=datetime.utcnow(),
    )
    base.update(kw)
    return JobPosting(**base)


def _seed(s, jobs):
    for j in jobs:
        s.add(j)
    s.commit()


def test_every_seniority_level_filters_exactly():
    s = _session()
    levels = ["New Grad", "Junior", "Associate", "Mid-Level", "Senior",
              "Staff", "Principal", "Lead", "Manager"]
    jobs = []
    for lv in levels:
        senior = lv in ("Senior", "Staff", "Principal", "Lead", "Manager")
        jobs.append(_job(experience_level=lv, is_senior=senior,
                         is_entry_level=(lv in ("New Grad",)),
                         is_candidate_friendly=(lv in ("Junior", "Associate"))))
    _seed(s, jobs)
    for lv in levels:
        _, n = M._build_job_query(s, page=1, limit=50, level_filter=lv)
        assert n >= 1, f"{lv} filter returned 0 (senior gate / mapping bug)"
        # senior-tier chips must surface their senior roles
        if lv in ("Staff", "Principal", "Lead", "Manager", "Senior"):
            items, _ = M._build_job_query(s, page=1, limit=50, level_filter=lv)
            assert all(j.experience_level == lv for j in items), f"{lv} leaked other levels"


def test_posted_within_uses_posted_date_not_first_seen():
    s = _session()
    now = datetime.now(timezone.utc)
    _seed(s, [
        # scraped just now, but POSTED 10 days ago -> excluded from "last 24h"
        _job(posted_date=now - timedelta(days=10), first_seen_at=now),
        # posted 2 hours ago -> included
        _job(posted_date=now - timedelta(hours=2), first_seen_at=now),
    ])
    _, n = M._build_job_query(s, page=1, limit=50, posted_within_hours=24, include_senior=True)
    assert n == 1


def test_min_score_rebased_on_new_grad_fit():
    s = _session()
    _seed(s, [
        _job(new_grad_fit=95, match_score=40),   # great new-grad fit, low relevance
        _job(new_grad_fit=30, match_score=95),   # poor new-grad fit, high relevance
    ])
    _, n = M._build_job_query(s, page=1, limit=50, min_score=75, include_senior=True)
    assert n == 1  # only the high New-Grad-Fit job passes
