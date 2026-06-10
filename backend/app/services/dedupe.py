"""Deduplication logic for job postings."""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from sqlmodel import Session, select

from ..models import JobPosting


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def make_fingerprint(company: str, job_title: str, location: str, job_id: str = "", apply_url: str = "") -> str:
    """Stable fingerprint used to detect duplicates."""
    if job_id:
        key = f"{_norm(company)}|{job_id}"
    elif apply_url:
        key = f"{_norm(company)}|{_norm(apply_url)}"
    else:
        key = f"{_norm(company)}|{_norm(job_title)}|{_norm(location)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def find_existing(
    session: Session,
    company: str,
    job_title: str,
    location: str,
    job_id: str = "",
    apply_url: str = "",
) -> Optional[JobPosting]:
    """Return an existing matching job record, or None."""
    # Primary: match by company + job_id
    if job_id:
        stmt = select(JobPosting).where(
            JobPosting.company == company,
            JobPosting.job_id_from_company == job_id,
        )
        result = session.exec(stmt).first()
        if result:
            return result

    # Secondary: match by apply URL
    if apply_url:
        stmt = select(JobPosting).where(
            JobPosting.company == company,
            JobPosting.apply_url == apply_url,
        )
        result = session.exec(stmt).first()
        if result:
            return result

    # Tertiary: fuzzy title + location match
    from ..scoring import normalize_title
    norm_title = normalize_title(job_title)
    norm_loc = _norm(location)

    stmt = select(JobPosting).where(JobPosting.company == company)
    candidates = session.exec(stmt).all()
    for job in candidates:
        if normalize_title(job.job_title) == norm_title and _norm(job.location) == norm_loc:
            return job

    return None
