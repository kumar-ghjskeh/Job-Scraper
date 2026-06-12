"""Idempotent backfill for the scoring/location overhaul.

For every stored job it: (1) ensures the new_grad_fit/experienced_fit columns
exist, (2) RE-PARSES the location with the fixed parser (so UK/foreign jobs that
were mis-flagged USA drop out), (3) recomputes the relevance score without the
USA boost, and (4) computes New Grad Fit + Experienced Fit.

Safe to re-run. Writes to whatever DATABASE_URL is set (local SQLite by default;
set it to the Render External URL to fix production).

    py -m backend.scripts.backfill_scores_locations
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from backend.app.database import engine  # noqa: E402
from backend.app.location_utils import parse_location  # noqa: E402
from backend.app.models import JobPosting  # noqa: E402
from backend.app.quality import canonical_location_label  # noqa: E402
from backend.app.scoring import (  # noqa: E402
    calculate_match_score, experienced_fit_score, new_grad_fit_score,
)


def _ensure_columns() -> None:
    is_pg = engine.dialect.name == "postgresql"
    ine = "IF NOT EXISTS " if is_pg else ""
    with engine.begin() as conn:
        for col in ("new_grad_fit", "experienced_fit"):
            try:
                conn.execute(text(
                    f"ALTER TABLE job_postings ADD COLUMN {ine}{col} INTEGER NOT NULL DEFAULT 0"
                ))
                print(f"  added column job_postings.{col}")
            except Exception as e:
                print(f"  column {col}: {str(e)[:60]} (likely already exists)")


def main() -> None:
    print(f"DB dialect: {engine.dialect.name}")
    _ensure_columns()

    with Session(engine) as s:
        jobs = s.exec(select(JobPosting)).all()
        usa_before = sum(1 for j in jobs if j.is_usa)
        flipped, ng_hist = 0, {"90+": 0, "75-89": 0, "60-74": 0, "46-59": 0, "<46": 0}

        for j in jobs:
            was_usa = j.is_usa
            loc = parse_location(j.location_raw or j.location or "", j.cleaned_description or "")
            j.is_usa = loc.is_usa
            j.is_remote_usa = loc.is_remote_usa
            j.country = loc.country
            j.state = loc.state
            j.city = loc.city
            j.location_confidence = loc.confidence
            j.location_label = canonical_location_label(
                j.location or "", loc.is_usa, loc.is_remote_usa, j.remote_status, loc.confidence
            )
            if was_usa and not j.is_usa:
                flipped += 1

            # Relevance without USA boost
            score, _kws, _bd = calculate_match_score(
                j.job_title, j.cleaned_description or "", j.company_priority,
                j.location or "", is_usa=loc.is_usa, first_seen_recently=False,
                ats_platform=j.ats_platform,
            )
            j.match_score = score

            ng = new_grad_fit_score(
                j.experience_level, j.is_senior, j.is_entry_level,
                j.is_candidate_friendly, j.years_required_min,
                j.job_title, j.cleaned_description or "",
            )
            j.new_grad_fit = ng
            j.experienced_fit = experienced_fit_score(
                j.experience_level, j.is_senior, j.years_required_min
            )
            bucket = ("90+" if ng >= 90 else "75-89" if ng >= 75 else "60-74"
                      if ng >= 60 else "46-59" if ng >= 46 else "<46")
            ng_hist[bucket] += 1
            s.add(j)

        s.commit()
        usa_after = sum(1 for j in jobs if j.is_usa)
        print(f"\nJobs processed   : {len(jobs)}")
        print(f"USA before/after : {usa_before} -> {usa_after}  (flipped foreign-out: {flipped})")
        print(f"New Grad Fit dist: {ng_hist}")


if __name__ == "__main__":
    main()
