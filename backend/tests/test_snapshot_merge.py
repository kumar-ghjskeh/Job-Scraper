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


def _retired(key: str, misses: int, seen: str) -> dict:
    return {
        "key": key, "company": "AMD", "job_title": "DV Engineer", "apply_url": "u",
        "active_status": "possibly_removed", "missed_scrapes": misses,
        "last_seen_at": seen, "first_seen_at": seen, "is_usa": True,
        "role_category": "Design Verification", "is_software_only": False,
    }


def test_merge_does_not_rewind_the_removal_counter(tmp_path):
    """last_seen_at cannot break the tie for a posting that was NOT seen.

    It does not advance while a posting is missing, so for every missing posting the
    two sides tied and `ours` won by default. The browser pass seeds from an older
    snapshot, so its stale missed_scrapes=1 overwrote the httpx pass's 2 on every
    cycle. The counter could never pass 1, nothing reached the threshold of 4, and no
    posting was ever marked `removed` — 1,137 rows sat at possibly_removed with
    missed_scrapes=1 and removed_at unset, so the retired set grew without bound.
    """
    seen = "2026-10-01T00:00:00+00:00"
    base = tmp_path / "base.json"
    ours = tmp_path / "ours.json"

    # httpx pass has advanced to 3; browser pass still holds the stale 1.
    _write(base, [_retired("k1", 3, seen)], [_company("AMD")], [])
    _write(ours, [_retired("k1", 1, seen)], [_company("AMD")], [])
    merge_snapshot_files(base, ours)
    got = json.loads(ours.read_text(encoding="utf-8"))["jobs"][0]
    assert got["missed_scrapes"] == 3, (
        "the publishing pass rewound the removal counter; postings can then never "
        "reach the threshold and are never retired"
    )

    # Symmetric: whichever side is further along wins.
    _write(base, [_retired("k1", 1, seen)], [_company("AMD")], [])
    _write(ours, [_retired("k1", 3, seen)], [_company("AMD")], [])
    merge_snapshot_files(base, ours)
    assert json.loads(ours.read_text(encoding="utf-8"))["jobs"][0]["missed_scrapes"] == 3


def test_a_fresher_sighting_still_resets_the_counter(tmp_path):
    """Keeping the higher counter must not override a genuine re-sighting: a posting
    seen again is active, and its miss count belongs back at zero."""
    base = tmp_path / "base.json"
    ours = tmp_path / "ours.json"
    _write(base, [_retired("k1", 3, "2026-10-01T00:00:00+00:00")], [_company("AMD")], [])
    fresh = _retired("k1", 0, "2026-10-02T00:00:00+00:00")
    fresh["active_status"] = "active"
    _write(ours, [fresh], [_company("AMD")], [])
    merge_snapshot_files(base, ours)
    got = json.loads(ours.read_text(encoding="utf-8"))["jobs"][0]
    assert got["missed_scrapes"] == 0 and got["active_status"] == "active"


def test_retired_rows_keep_every_field_the_state_machine_needs():
    """Retired rows are stripped to cut the payload; the strip must not drop a field
    the removal pass or the merge reads back."""
    from backend.app.snapshot import RETIRED_ROW_FIELDS
    for f in ("key", "company", "job_title", "apply_url", "job_id_from_company",
              "active_status", "missed_scrapes", "last_seen_at", "removed_at"):
        assert f in RETIRED_ROW_FIELDS, f"{f} must survive on a retired row"


def test_removed_rows_are_exported_so_retirement_can_stick(tmp_path, monkeypatch):
    """Retirement was structurally impossible, and this is the assertion that says why.

    build_snapshot used to select only active + possibly_removed. So a job that hit
    removed_job_threshold became `removed` in the scratch database, got DROPPED from
    the export, and was then restored from the published corpus by the merge — which
    unions the two sides. Every static run reported `removed: 623` while the published
    corpus held zero removed rows and 1,344 rows sat permanently at missed_scrapes=1,
    with no status change between consecutive runs. The corpus could only grow, and
    purge_removed_jobs() could never find anything to purge.
    """
    import importlib
    from datetime import datetime, timezone

    from sqlmodel import Session

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    from backend.app import config
    importlib.reload(config)
    from backend.app import database
    importlib.reload(database)
    from backend.app import snapshot as snap
    importlib.reload(snap)
    from backend.app.models import ActiveStatus, JobPosting

    database.init_db()
    with Session(database.engine) as s:
        s.add(JobPosting(
            company="AMD", job_title="DV Engineer", apply_url="https://x/1",
            job_id_from_company="1", active_status=ActiveStatus.removed,
            missed_scrapes=6, removed_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        ))
        s.commit()
        payload, _details = snap.build_snapshot(s)

    statuses = {r.get("active_status") for r in payload["jobs"]}
    assert "removed" in statuses, (
        "build_snapshot dropped the removed row. The merge then resurrects it from "
        "the published corpus and retirement never takes effect."
    )
    # And it must still be stripped, so exporting them does not re-inflate the file.
    removed = [r for r in payload["jobs"] if r.get("active_status") == "removed"][0]
    assert set(removed) <= snap.RETIRED_ROW_FIELDS, (
        f"removed row carries unexpected fields: {set(removed) - snap.RETIRED_ROW_FIELDS}"
    )
    assert removed["missed_scrapes"] == 6

    # Restore the module state for the rest of the suite.
    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(database)
    importlib.reload(snap)


def test_the_merge_lets_a_miss_count_advance_across_runs(tmp_path):
    """The behaviour the previous test protects, stated over two cycles.

    Each run rebuilds a scratch database from the published corpus, so a counter that
    does not survive the merge can never reach any threshold. Verified over real
    cycles: 1 -> 2 -> 3 ... -> 6 -> removed, where it previously stuck at 1.
    """
    seen = "2026-10-01T00:00:00+00:00"
    published = tmp_path / "published.json"
    _write(published, [_retired("k1", 1, seen)], [_company("AMD")], [])

    for expected in (2, 3, 4):
        ours = tmp_path / f"ours{expected}.json"
        # What the run produces: the same posting, missed once more.
        _write(ours, [_retired("k1", expected, seen)], [_company("AMD")], [])
        merge_snapshot_files(published, ours)
        published.write_bytes(ours.read_bytes())
        got = _json_load(published)["jobs"][0]["missed_scrapes"]
        assert got == expected, (
            f"miss count regressed to {got} instead of {expected}; retirement cannot "
            "progress if the merge does not carry it forward"
        )


def _json_load(path):
    import json as _json
    return _json.loads(path.read_text(encoding="utf-8"))
