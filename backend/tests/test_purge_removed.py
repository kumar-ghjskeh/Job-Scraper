"""Retired postings must eventually be deleted, or the corpus grows forever.

Nothing ever deleted a job row. Retiring one only changed its status, so every
posting the scraper had ever seen stayed in the corpus permanently: the published
file only grew, and each scrape seeded a database that was increasingly dead rows.
Stripping retired rows to 11 fields cut what each one costs but not how many there
are.

The purge is gated on a successful scrape for the same reason the stale sweep is —
during an outage every posting looks dead, and deleting then is not recoverable.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture()
def db(monkeypatch):
    tmp = tempfile.mkdtemp(prefix="purge-test-")
    prior = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/t.db"
    import importlib

    from backend.app import config
    importlib.reload(config)
    from backend.app import database
    importlib.reload(database)
    from backend.app import scrape_engine
    importlib.reload(scrape_engine)
    database.init_db()
    yield database, scrape_engine
    if prior is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = prior
    importlib.reload(config)
    importlib.reload(database)
    importlib.reload(scrape_engine)


def _add(session, models, **over):
    row = {
        "company": "AMD", "job_title": "DV Engineer", "apply_url": "https://x",
        "active_status": models.ActiveStatus.removed,
        "removed_at": datetime.now(timezone.utc) - timedelta(days=90),
        "last_seen_at": datetime.now(timezone.utc) - timedelta(days=90),
    }
    row.update(over)
    job = models.JobPosting(**row)
    session.add(job)
    return job


def test_long_removed_postings_are_deleted(db):
    database, scrape_engine = db
    from sqlmodel import Session, select

    from backend.app import models

    with Session(database.engine) as s:
        _add(s, models)                                   # removed 90 days ago
        _add(s, models, apply_url="https://y")            # removed 90 days ago
        s.commit()

    assert scrape_engine.purge_removed_jobs(max_age_days=60) == 2
    with Session(database.engine) as s:
        assert s.exec(select(models.JobPosting)).all() == []


def test_recently_removed_and_active_postings_survive(db):
    """Only the long-dead go. A recently retired posting is still useful context,
    and an active one must never be touched by this."""
    database, scrape_engine = db
    from sqlmodel import Session, select

    from backend.app import models

    with Session(database.engine) as s:
        _add(s, models, apply_url="https://recent",
             removed_at=datetime.now(timezone.utc) - timedelta(days=5))
        _add(s, models, apply_url="https://live",
             active_status=models.ActiveStatus.active, removed_at=None)
        _add(s, models, apply_url="https://maybe",
             active_status=models.ActiveStatus.possibly_removed, removed_at=None)
        s.commit()

    assert scrape_engine.purge_removed_jobs(max_age_days=60) == 0
    with Session(database.engine) as s:
        assert len(s.exec(select(models.JobPosting)).all()) == 3


def test_a_removed_posting_with_no_timestamp_is_not_deleted(db):
    """removed_at was missing from the export for a long time, so older rows carry
    none. Deleting on a NULL timestamp would wipe exactly the oldest history with no
    way to tell whether it qualified."""
    database, scrape_engine = db
    from sqlmodel import Session, select

    from backend.app import models

    with Session(database.engine) as s:
        _add(s, models, apply_url="https://notimestamp", removed_at=None)
        s.commit()

    assert scrape_engine.purge_removed_jobs(max_age_days=60) == 0
    with Session(database.engine) as s:
        assert len(s.exec(select(models.JobPosting)).all()) == 1


def test_purge_runs_only_after_a_successful_scrape():
    """During an outage every posting looks dead. The sweep already carries this
    guarantee; the purge is destructive, so it must sit behind the same gate."""
    import inspect

    from backend.app import run_static

    src = inspect.getsource(run_static._finish)
    gate = src.index("if scraped_ok:")
    assert src.index("purge_removed_jobs()") > gate, (
        "purge_removed_jobs is called outside the scraped_ok guard — an outage would "
        "then permanently delete rows that only looked dead"
    )
