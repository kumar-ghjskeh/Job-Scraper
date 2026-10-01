"""Merging two passes' snapshots must not shrink what the other pass found.

Three workflows publish the same two files — httpx, curl_cffi and the browser pass —
and whichever finishes last merges its corpus into what is already committed. The
merge unioned the JOB rows correctly but not the metadata around them, so publishing
quietly discarded the other passes' work in two visible ways:

  1. Only `usa_active_jobs` was recomputed over the union. Every other tally kept the
     publishing run's value, computed over that run's own slice of companies. After
     the browser pass (8 companies) published, HPE — scraped by the httpx pass
     minutes earlier — read total_active_jobs=0, auto_connected=false and
     scrape_status="idle" next to usa_active_jobs=20. The directory showed
     "no openings" for a source that had just returned twenty US jobs.

  2. `runs` was taken from the publishing side wholesale, so the httpx and curl_cffi
     run entries vanished the moment the browser pass published. Data Health then
     reported those engines as hours stale when they had just succeeded — the exact
     false alarm this project has already chased once.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.snapshot import (
    HIDDEN_CATEGORIES,
    company_tallies,
    merge_snapshot_files,
)

BROWSER_COMPANIES = {"Arm", "Cisco", "Quadric"}


def _job(company: str, key: str, usa: bool = True, cat: str = "Design Verification") -> dict:
    return {
        "key": key, "company": company, "is_usa": usa, "active_status": "active",
        "role_category": cat, "is_software_only": False, "is_entry_level": False,
        "is_candidate_friendly": False, "data_quality_score": 80,
        "first_seen_at": "2026-10-01T00:00:00+00:00", "posted_date_known": False,
        "last_seen_at": "2026-10-01T00:00:00+00:00",
    }


def _company(name: str, **over) -> dict:
    base = {
        "name": name, "total_active_jobs": 0, "usa_active_jobs": 0,
        "viewable_jobs": 0, "entry_level_jobs": 0, "new_jobs_today": 0,
        "parser_confidence": 0, "auto_connected": False, "scrape_status": "idle",
        "scrape_error_count": 0, "consecutive_empty_scrapes": 0,
    }
    base.update(over)
    return base


def _write(path: Path, jobs, companies, runs) -> None:
    path.write_text(json.dumps(
        {"generated_at": "2026-10-01T00:00:00+00:00", "count": len(jobs),
         "jobs": jobs, "companies": companies, "runs": runs}), encoding="utf-8")


def test_merge_restores_tallies_for_companies_the_publisher_never_saw(tmp_path):
    """The HPE case: scraped by another pass, reported as having nothing."""
    base_jobs = [_job("Hewlett Packard Enterprise", f"hpe-{i}") for i in range(20)]
    base_jobs += [_job("Arm", "arm-1")]
    base = tmp_path / "base.json"
    _write(base, base_jobs,
           [_company("Hewlett Packard Enterprise", total_active_jobs=20,
                     usa_active_jobs=20, auto_connected=True, scrape_status="ok"),
            _company("Arm")],
           [{"triggered_by": "static", "started_at": "2026-10-01T10:00:00+00:00"}])

    # The browser pass knows only its own companies, so its view of HPE is empty.
    ours = tmp_path / "ours.json"
    _write(ours, [_job("Arm", "arm-1")],
           [_company("Hewlett Packard Enterprise"), _company("Arm")],
           [{"triggered_by": "browser", "started_at": "2026-10-01T11:00:00+00:00"}])

    merge_snapshot_files(base, ours)
    out = json.loads(ours.read_text(encoding="utf-8"))
    hpe = {c["name"]: c for c in out["companies"]}["Hewlett Packard Enterprise"]

    assert hpe["total_active_jobs"] == 20, (
        "total_active_jobs was not recomputed over the union, so a company scraped "
        "by another pass still reports zero openings"
    )
    assert hpe["usa_active_jobs"] == 20
    assert hpe["auto_connected"] is True, "would render as a dead source"
    assert hpe["scrape_status"] == "ok", "would render as 'No openings'"


def test_merge_keeps_both_passes_run_history(tmp_path):
    """Losing a run entry makes a healthy engine look stale in Data Health."""
    base = tmp_path / "base.json"
    _write(base, [_job("Arm", "arm-1")], [_company("Arm")], [
        {"triggered_by": "static", "started_at": "2026-10-01T10:00:00+00:00"},
        {"triggered_by": "cf", "started_at": "2026-10-01T10:30:00+00:00"},
    ])
    ours = tmp_path / "ours.json"
    _write(ours, [_job("Arm", "arm-1")], [_company("Arm")], [
        {"triggered_by": "browser", "started_at": "2026-10-01T11:00:00+00:00"},
    ])

    merge_snapshot_files(base, ours)
    out = json.loads(ours.read_text(encoding="utf-8"))
    engines = {r["triggered_by"] for r in out["runs"]}
    assert engines == {"static", "cf", "browser"}, (
        f"run history lost an engine: {engines}. Data Health derives each engine's "
        "freshness from these entries, so dropping one reports a working engine as "
        "hours stale."
    )
    # Newest first, so the freshness calculation reads the right one.
    starts = [r["started_at"] for r in out["runs"]]
    assert starts == sorted(starts, reverse=True)


def test_physical_design_is_not_counted_as_viewable():
    """The directory's "viewable" count must agree with what the UI shows.

    Physical Design was moved out of RTL/DV scope and added to the frontend's hidden
    set; this set has to match or the per-company counts promise roles the list view
    never displays.
    """
    assert "Physical Design" in HIDDEN_CATEGORIES
    rows = [
        _job("X", "a", cat="Design Verification"),
        _job("X", "b", cat="Physical Design"),
    ]
    st = company_tallies(rows)["X"]
    assert st["total"] == 2, "both postings are still real and still counted"
    assert st["viewable"] == 1, "the Physical Design row must not be viewable"


def test_tallies_ignore_retired_postings():
    rows = [_job("X", "a"), {**_job("X", "b"), "active_status": "possibly_removed"}]
    st = company_tallies(rows)["X"]
    assert st["total"] == 1 and st["usa"] == 1
