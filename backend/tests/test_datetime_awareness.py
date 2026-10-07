"""Every stored datetime must be timezone-aware.

The models originally defaulted to ``datetime.utcnow()`` (naive) while the rest
of the codebase compared against ``datetime.now(timezone.utc)`` (aware). Mixing
the two is a latent type error: it works until a dependency decides to validate
it. sqlmodel 0.0.47 did exactly that — "Datetime values must have timezone
information" — and because the offending comparison runs at the very start of
every scrape, in maintain_scrape_runs(), it killed every engine before a single
company was fetched. Nine days of failed runs, with the same code passing
locally on sqlmodel 0.0.38.

These tests make the class of bug visible at commit time rather than on a
scheduled run days later. They need no database.
"""

from __future__ import annotations

import inspect
import re
from datetime import datetime, timedelta, timezone

from backend.app import models, scrape_engine, snapshot

# Model fields that persist a timestamp. All of them must default to the shared
# aware factory.
_TIMESTAMP_MODELS = [
    models.JobPosting,
    models.ResumeProfile,
    models.Setting,
    models.Watchlist,
    models.ScrapeRun,
    models.ScrapeError,
]


def test_shared_factory_returns_aware_utc():
    now = models.utcnow()
    assert now.tzinfo is not None, "models.utcnow() must be timezone-aware"
    assert now.utcoffset() == timedelta(0), "models.utcnow() must be UTC"


def test_no_model_defaults_to_a_naive_datetime():
    """Catch a new field added with datetime.utcnow — the original mistake."""
    offenders: list[str] = []
    for model in _TIMESTAMP_MODELS:
        for name, field in model.model_fields.items():
            factory = getattr(field, "default_factory", None)
            if factory is None:
                continue
            try:
                value = factory()
            except Exception:
                continue
            if isinstance(value, datetime) and value.tzinfo is None:
                offenders.append(f"{model.__name__}.{name}")
    assert not offenders, (
        "These fields default to a NAIVE datetime: "
        + ", ".join(offenders)
        + ". Use models.utcnow(); a naive default is rejected by sqlmodel >=0.0.47 "
        "and silently breaks every comparison against an aware value."
    )


def test_source_does_not_reintroduce_utcnow():
    """datetime.utcnow() must not reappear in the scrape path.

    Checked on source because the failure only shows up at runtime, against a
    library version that may not be the one installed locally.
    """
    pattern = re.compile(r"datetime\.utcnow\s*\(")
    for module in (models, scrape_engine, snapshot):
        src = inspect.getsource(module)
        # Strip docstrings/comments: the history is deliberately described there.
        code = "\n".join(
            line for line in src.splitlines()
            if not line.lstrip().startswith("#") and "``" not in line
        )
        hits = [m for m in pattern.findall(code)]
        assert not hits, (
            f"{module.__name__} calls datetime.utcnow(). Use "
            "datetime.now(timezone.utc) (or models.utcnow() for a model default) "
            "so stored and compared values share one awareness."
        )


def test_zombie_run_cutoff_is_aware():
    """The exact comparison that broke: started_at < cutoff in maintain_scrape_runs."""
    src = inspect.getsource(scrape_engine.maintain_scrape_runs)
    assert "datetime.now(timezone.utc)" in src, (
        "maintain_scrape_runs builds its cutoff from a naive clock again. It "
        "compares against ScrapeRun.started_at, which is aware, and runs before "
        "any scraping — so getting this wrong takes down every engine at once."
    )


def test_snapshot_restores_aware_datetimes():
    """Snapshots written before the fix hold naive strings; restoring them must
    not reintroduce naive values into a freshly built database.

    Asserted on behaviour rather than on the source of one function: the parser
    was lifted out of load_snapshot_into_db to module scope so the company-health
    restore could share it, and a source-text check broke on that refactor while
    the guarantee itself was intact. Behaviour is what matters here.
    """
    assert hasattr(snapshot, "_parse_aware"), (
        "the shared timestamp parser is gone; whatever replaced it must still "
        "coerce naive values to UTC on the way into the database"
    )
    naive = snapshot._parse_aware("2026-01-01T00:00:00")
    assert naive is not None and naive.tzinfo is not None, (
        "a stored timestamp WITHOUT an offset was restored as naive. Older "
        "snapshots are written that way, so this reseeds the mixed-awareness bug "
        "that killed every scrape for nine days."
    )
    assert naive.utcoffset() == timedelta(0), "must be read as UTC, not local time"

    aware = snapshot._parse_aware("2026-01-01T00:00:00+05:30")
    assert aware is not None and aware.utcoffset() == timedelta(hours=5, minutes=30), (
        "an explicit offset must be preserved, not overwritten with UTC"
    )
    assert snapshot._parse_aware(None) is None
    assert snapshot._parse_aware("not a date") is None


def test_every_exported_datetime_field_is_coerced_on_restore():
    """A datetime column added to LIST_FIELDS must also be coerced back from its
    ISO string, or every scrape dies on the seed.

    removed_at was added to the export when retirement was fixed and NOT added to
    the coercion list. The bug was invisible for days because the column was null on
    every row — nothing had ever actually reached `removed`. The moment retirement
    started working, 567 rows gained a real timestamp and the next three scheduled
    runs all failed with:

        SQLite DateTime type only accepts Python datetime and date objects as input

    The coercion list is now DERIVED from the model, so adding a column cannot miss
    it. This asserts the derivation still finds them: it returned an empty tuple
    twice while I was writing it, because these columns use the UtcDateTime
    TypeDecorator, whose python_type raises NotImplementedError and which is not an
    instance of sqlalchemy.DateTime. An empty list fails exactly as the hand-written
    tuple did, only more quietly.
    """
    from sqlalchemy import Date, DateTime

    from backend.app.models import JobPosting, UtcDateTime

    expected = {
        col.name
        for col in JobPosting.__table__.columns  # type: ignore[attr-defined]
        if col.name in snapshot.LIST_FIELDS
        and isinstance(col.type, (UtcDateTime, DateTime, Date))
    }
    assert expected, (
        "the derivation found no datetime columns at all — it is silently matching "
        "nothing, which reintroduces the original bug"
    )
    assert "removed_at" in expected, "the field that caused the outage must be covered"
    missing = expected - set(snapshot._EXPORTED_DATETIME_FIELDS)
    assert not missing, (
        f"exported datetime columns that are NOT coerced on restore: {sorted(missing)}. "
        "Every scrape will fail on the seed as soon as any row has a value."
    )


def test_restoring_a_row_with_every_datetime_populated_works():
    """Behavioural half: the exact insert that was failing in CI."""
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "key": "k1", "company": "AMD", "job_title": "DV Engineer",
        "apply_url": "https://x/1", "job_id_from_company": "1",
        "active_status": "removed", "missed_scrapes": 6,
        # All four, as strings — which is how the corpus stores them.
        "posted_date": now, "first_seen_at": now, "last_seen_at": now,
        "removed_at": now,
    }
    tmp = Path(tempfile.mkdtemp()) / "jobs.json"
    tmp.write_text(json.dumps({"generated_at": now, "count": 1, "jobs": [row],
                               "companies": [], "runs": []}), encoding="utf-8")
    # Only the coercion matters here, so assert on it directly rather than standing
    # up a database: a string reaching the column is what SQLite rejects.
    for field in snapshot._EXPORTED_DATETIME_FIELDS:
        if field in row:
            parsed = snapshot._parse_aware(row[field])
            assert isinstance(parsed, datetime), f"{field} was not coerced"
            assert parsed.tzinfo is not None, f"{field} came back naive"
