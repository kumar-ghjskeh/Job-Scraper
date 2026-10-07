"""Per-company health must survive the scratch-database rebuild.

The quarantine machinery existed but had never once fired. Each run builds a fresh
scratch SQLite, and nothing ever created Company rows in it, so every
`select(Company)` in the scrape path returned None:

  * the quarantine check `co and co.scrape_error_count >= THRESHOLD` was always
    False, so a permanently broken source was retried on every run forever;
  * the failure handler's `if co: co.scrape_error_count += 1` recorded nothing, so
    counts never rose above zero;
  * Data Health's broken-source panel was structurally always empty, which is why
    it had never flagged anything.

This matters now because the DOM-scraped sources being added fail SILENTLY: a
selector stops matching, the adapter raises nothing and returns an empty list, and
the run counts the company as scraped successfully.

These tests use a temporary SQLite file and no network.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from backend.app.scrape_engine import EMPTY_STALL_THRESHOLD, ERROR_QUARANTINE_THRESHOLD


def _rebuild_modules(db_url: str):
    """Point the whole stack at a different database.

    `config.settings` is instantiated at import time, so reloading `database`
    alone keeps the old engine and the test silently runs against the dev
    database — which is how this fixture failed the first time.
    """
    import importlib

    os.environ["DATABASE_URL"] = db_url
    from backend.app import config
    importlib.reload(config)
    from backend.app import database
    importlib.reload(database)
    from backend.app import snapshot
    importlib.reload(snapshot)
    database.init_db()
    return database, snapshot


@pytest.fixture()
def fresh_db(monkeypatch):
    """A brand-new scratch database, as every scrape run starts with."""
    tmp = tempfile.mkdtemp(prefix="quarantine-test-")
    prior = os.environ.get("DATABASE_URL")
    database, snapshot = _rebuild_modules(f"sqlite:///{tmp}/t.db")
    yield tmp, database, snapshot
    # Leave the process pointing where it started, so module reloads inside one
    # test cannot leak a temp database into the rest of the suite.
    if prior is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = prior
    _rebuild_modules(prior or f"sqlite:///{Path('data/jobs.db')}")


def test_company_rows_are_created_at_all(fresh_db):
    """The bug in one assertion: this count used to be zero on every run."""
    _tmp, database, snapshot = fresh_db
    from sqlmodel import Session, select

    from backend.app.models import Company

    created = snapshot.seed_companies_into_db("frontend/public/data/jobs.json")
    assert created > 0, "no Company rows were seeded — quarantine has nothing to read"
    with Session(database.engine) as s:
        assert len(s.exec(select(Company)).all()) == created


def test_health_counters_survive_a_rebuild(fresh_db, tmp_path):
    """Counters must come back from the snapshot, or they reset to zero every run
    and no threshold is ever reachable."""
    _tmp, database, snapshot = fresh_db
    from sqlmodel import Session, select

    from backend.app.models import Company

    snapshot.seed_companies_into_db("frontend/public/data/jobs.json")

    with Session(database.engine) as s:
        rows = s.exec(select(Company)).all()
        broken, stalled = rows[0], rows[1]
        broken_name, stalled_name = broken.name, stalled.name
        broken.scrape_error_count = ERROR_QUARANTINE_THRESHOLD + 1
        stalled.consecutive_empty_scrapes = EMPTY_STALL_THRESHOLD + 2
        s.add(broken)
        s.add(stalled)
        s.commit()
        payload, _details = snapshot.build_snapshot(s)

    exported = {c["name"]: c for c in payload["companies"]}
    assert exported[broken_name]["quarantined"] is True
    assert exported[broken_name]["scrape_status"] == "quarantined"
    assert exported[stalled_name]["scrape_status"] == "stalled"
    assert (exported[stalled_name]["consecutive_empty_scrapes"]
            == EMPTY_STALL_THRESHOLD + 2)

    # Rebuild from that snapshot, exactly as the next run would.
    snap = tmp_path / "jobs.json"
    snap.write_text(json.dumps(payload), encoding="utf-8")

    tmp2 = tempfile.mkdtemp(prefix="quarantine-test2-")
    db2, sn2 = _rebuild_modules(f"sqlite:///{tmp2}/t.db")
    sn2.seed_companies_into_db(snap)

    with Session(db2.engine) as s2:
        back = {c.name: c for c in s2.exec(select(Company)).all()}
    assert back[broken_name].scrape_error_count == ERROR_QUARANTINE_THRESHOLD + 1, (
        "error count did not survive the rebuild, so quarantine can never trigger"
    )
    assert back[stalled_name].consecutive_empty_scrapes == EMPTY_STALL_THRESHOLD + 2


def test_a_stalled_source_is_not_quarantined(fresh_db):
    """A board really can be empty. Stalling is reported, never skipped — skipping
    would mean never noticing when it refills."""
    _tmp, _database, snapshot = fresh_db
    from sqlmodel import Session, select

    from backend.app.database import engine
    from backend.app.models import Company

    snapshot.seed_companies_into_db("frontend/public/data/jobs.json")
    with Session(engine) as s:
        c = s.exec(select(Company)).first()
        name = c.name
        c.consecutive_empty_scrapes = EMPTY_STALL_THRESHOLD + 50
        c.scrape_error_count = 0
        s.add(c)
        s.commit()
        payload, _ = snapshot.build_snapshot(s)
    row = {x["name"]: x for x in payload["companies"]}[name]
    assert row["quarantined"] is False, "an empty board must not be auto-skipped"
    assert row["scrape_status"] == "stalled"


def test_scrape_path_tracks_empty_results():
    """The increment/reset must exist in the scrape loop, not only in the model."""
    import inspect

    from backend.app import scrape_engine

    src = inspect.getsource(scrape_engine.run_scrape)
    assert "consecutive_empty_scrapes = 0" in src, (
        "a successful non-empty fetch must RESET the stall counter, or a source "
        "that recovers stays flagged forever"
    )
    assert "consecutive_empty_scrapes += 1" in src, (
        "an empty-but-successful fetch must increment the stall counter — this is "
        "the silent failure mode of DOM scraping"
    )


def test_stall_is_judged_on_the_source_not_on_our_filter():
    """A healthy board with no matching openings is not a stalled source.

    The counter used to read what fetch_jobs() returned, which is already past the
    adapter's relevance filter — so these two cases were indistinguishable:

        selector broke        source returns nothing            -> a real stall
        no RTL/DV openings    source returns jobs, none match   -> perfectly healthy

    Four of six flagged sources were the second kind. Western Digital answers with
    340 live postings and none are RTL/DV, because that work went to Sandisk in the
    split; Kioxia, Axelera AI and Lemurian Labs are the same shape at 19, 8 and 6.
    A 67% false-positive rate makes the flag worth ignoring, which defeats the point
    of having it.
    """
    import inspect

    from backend.app import run_browser_scrape, scrape_engine
    from backend.app.scrapers.base import BaseScraper

    assert "last_raw_count" in inspect.getsource(BaseScraper._filter_relevant), (
        "_filter_relevant no longer records the pre-filter count, so the stall "
        "counter has nothing to distinguish a dead source from an unmatched one"
    )
    for mod in (scrape_engine.run_scrape, run_browser_scrape.run_browser_scrape):
        src = inspect.getsource(mod)
        assert "last_raw_count" in src, (
            f"{mod.__qualname__} judges stalls on the filtered result again; a "
            "company with a live board and no matching roles will be reported as "
            "broken"
        )


def test_filter_relevant_records_the_pre_filter_count():
    """Behavioural half of the guard above."""
    from backend.app.scrapers.base import BaseScraper, JobData

    class _Concrete(BaseScraper):           # BaseScraper is abstract
        async def fetch_jobs(self):           # pragma: no cover - never called
            return []

    sc = _Concrete.__new__(_Concrete)
    sc.company_name = "Test"
    sc.last_raw_count = None
    jobs = [
        JobData(job_title="Design Verification Engineer", apply_url="https://x/1"),
        JobData(job_title="Office Manager", apply_url="https://x/2"),
        JobData(job_title="Account Executive", apply_url="https://x/3"),
    ]
    kept = BaseScraper._filter_relevant(sc, jobs)
    assert sc.last_raw_count == 3, "must record what the SOURCE returned"
    assert len(kept) < 3, "the non-engineering rows should have been filtered out"
