"""Export the scraped corpus to static JSON for the frontend to consume.

Why this exists
---------------
The job corpus is fully derived from public career sites and is tiny — about
150 KB gzipped for the fields the list renders. Serving it from a hosted
Postgres meant every page view and every scrape spent a metered network budget,
which exhausted the free-tier transfer quota three times and took the whole app
down with it. A static file on the CDN that already serves the frontend has no
such meter, costs nothing, and keeps working (with the last good data) even when
a scrape fails.

Two files, so opening the app is cheap and reading a posting is still complete:

    jobs.json     every active job, list/filter/sort fields only
    details.json  id -> full description text, fetched lazily on first open

Each job carries ``key`` — the same content fingerprint the deduper uses. It is
stable across rebuilds, unlike a database row id, so the browser can attach
saved/applied marks and notes to a posting and keep them when the corpus is
rebuilt from scratch.
"""

from __future__ import annotations

import gzip
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from .database import engine
from .models import ActiveStatus, Company, JobPosting, ScrapeRun
from .services.dedupe import make_fingerprint

logger = logging.getLogger(__name__)

# Fields the job list, filters, sorting and the details header need. Deliberately
# excludes the two large text columns — those live in details.json.
LIST_FIELDS = (
    "id", "company", "company_category", "company_priority", "job_title",
    "normalized_title", "role_category", "experience_level",
    "is_entry_level", "is_candidate_friendly", "is_senior",
    "years_required_min", "years_required_max",
    "location", "display_location", "remote_status", "is_usa", "is_remote_usa",
    "country", "state", "city", "location_confidence", "location_label",
    "job_id_from_company", "apply_url", "safe_apply_url", "source_url",
    "ats_platform", "apply_url_status",
    "posted_date", "posted_date_known", "first_seen_at", "last_seen_at",
    "match_score", "new_grad_fit", "experienced_fit", "matched_keywords",
    "job_skills", "relevance_score_label", "relevance_reason",
    "description_snippet", "is_software_only", "role_flags_json",
    "eligibility_risk", "eligibility_terms",
    "seniority_confidence", "classification_confidence", "data_quality_score",
    "source_reliability",
    # Carried so the removal state machine survives a rebuild: without these a
    # posting that flickers out of a source would reset its miss counter every
    # run and could never be retired.
    "active_status", "missed_scrapes",
)


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, datetime) else v


def build_snapshot(session: Session) -> tuple[dict, dict]:
    """Return ``(jobs_payload, details_payload)`` for the active corpus."""
    # possibly_removed rows are included so their miss counter persists; the
    # frontend shows only active ones.
    jobs = session.exec(
        select(JobPosting).where(
            JobPosting.active_status.in_([ActiveStatus.active, ActiveStatus.possibly_removed])
        )
    ).all()

    out: list[dict] = []
    details: dict[str, str] = {}
    for j in jobs:
        row = {f: _iso(getattr(j, f, None)) for f in LIST_FIELDS if hasattr(j, f)}
        # Stable identity so browser-held marks survive a full rebuild.
        row["key"] = make_fingerprint(
            j.company or "", j.job_title or "", j.location or "",
            j.job_id_from_company or "", j.apply_url or "",
        )
        out.append(row)
        body = (j.cleaned_description or "").strip()
        if body:
            details[str(j.id)] = body

    # Companies come from the YAML config, not the companies table: the config is
    # the source of truth, and the table may be unseeded on a freshly built
    # database. DB rows only contribute live scrape status when present.
    from .config import load_all_companies
    status = {
        c.name: {"last_scraped_at": _iso(c.last_scraped_at),
                 "scrape_error_count": c.scrape_error_count}
        for c in session.exec(select(Company)).all()
    }
    counts: dict[str, int] = {}
    for row in out:
        if row.get("is_usa") and str(row.get("active_status", "")).endswith("active"):
            counts[row["company"]] = counts.get(row["company"], 0) + 1
    companies = []
    for c in load_all_companies():
        name = c.get("name", "")
        companies.append({
            "name": name,
            "category": c.get("category", ""),
            "priority": c.get("priority", "C"),
            "careers_url": c.get("careers_url", ""),
            "ats_platform": c.get("ats_platform", ""),
            "engine": c.get("engine", ""),
            "enabled": bool(c.get("enabled", True)),
            "usa_active_jobs": counts.get(name, 0),
            **status.get(name, {"last_scraped_at": None, "scrape_error_count": 0}),
        })
    runs = [
        {"id": r.id, "started_at": _iso(r.started_at), "finished_at": _iso(r.finished_at),
         "companies_scraped": r.companies_scraped, "jobs_found": r.jobs_found,
         "new_jobs": r.new_jobs, "removed_jobs": r.removed_jobs,
         "errors": r.errors, "triggered_by": r.triggered_by}
        for r in session.exec(
            select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(20)
        ).all()
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(out),
        "jobs": out,
        "companies": companies,
        "runs": runs,
    }
    return payload, {"generated_at": payload["generated_at"], "descriptions": details}


def write_snapshot(out_dir: str | Path) -> dict:
    """Write jobs.json + details.json. Returns a small report for the log."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with Session(engine) as session:
        jobs_payload, details_payload = build_snapshot(session)

    report = {}
    for name, payload in (("jobs.json", jobs_payload), ("details.json", details_payload)):
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        (out_dir / name).write_bytes(raw)
        report[name] = {"bytes": len(raw), "gzip": len(gzip.compress(raw, 6))}
    report["count"] = jobs_payload["count"]
    logger.info(
        "snapshot: %s jobs — jobs.json %.0f KB (%.0f KB gz), details.json %.0f KB (%.0f KB gz)",
        report["count"],
        report["jobs.json"]["bytes"] / 1024, report["jobs.json"]["gzip"] / 1024,
        report["details.json"]["bytes"] / 1024, report["details.json"]["gzip"] / 1024,
    )
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    import sys
    print(json.dumps(write_snapshot(sys.argv[1] if len(sys.argv) > 1 else "snapshot"), indent=2))


# ── Rebuilding the working database from a snapshot ───────────────────────────

def load_snapshot_into_db(jobs_path: str | Path, details_path: str | Path | None = None) -> int:
    """Seed an empty database from jobs.json (+ details.json).

    This is what makes the static files the system of record. Each scrape run
    starts by rebuilding a scratch SQLite database from the committed snapshot,
    scrapes into it, and writes a new snapshot — so no hosted database is
    involved anywhere, and nothing has to be persisted between runs except two
    text files that diff and compress well.

    Only fields the scraper needs to carry forward are restored — notably
    ``first_seen_at`` (so "Added" dates stay honest) and ``missed_scrapes`` (so a
    posting that vanishes is still retired on schedule).
    """
    jobs_path = Path(jobs_path)
    if not jobs_path.exists():
        logger.info("no snapshot at %s — starting from an empty corpus", jobs_path)
        return 0
    payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    bodies: dict[str, str] = {}
    if details_path and Path(details_path).exists():
        bodies = json.loads(Path(details_path).read_text(encoding="utf-8")).get("descriptions", {})

    def _dt(v):
        if not v:
            return None
        try:
            return datetime.fromisoformat(str(v))
        except ValueError:
            return None

    restored = 0
    with Session(engine) as session:
        cols = {c.name for c in JobPosting.__table__.columns}  # type: ignore[attr-defined]
        for row in payload.get("jobs", []):
            data = {k: v for k, v in row.items() if k in cols and k != "id"}
            for f in ("posted_date", "first_seen_at", "last_seen_at"):
                if f in data:
                    data[f] = _dt(data[f])
            data.setdefault("first_seen_at", datetime.now(timezone.utc))
            data.setdefault("last_seen_at", datetime.now(timezone.utc))
            body = bodies.get(str(row.get("id", "")), "")
            if body:
                data["cleaned_description"] = body
            session.add(JobPosting(**data))
            restored += 1
        session.commit()
    logger.info("restored %d job(s) from %s", restored, jobs_path)
    return restored


# ── Merging concurrent publishes ──────────────────────────────────────────────

def merge_snapshot_files(base_jobs: str | Path, ours_jobs: str | Path,
                         base_details: str | Path | None = None,
                         ours_details: str | Path | None = None) -> dict:
    """Union another snapshot into ours, in place.

    Two scrape runs (browserless and browser) publish the same two files. Each
    regenerates the whole corpus from its own scratch database, so git cannot
    auto-merge them and a plain "last writer wins" would be destructive: the
    browser pass only knows about 3 companies, so publishing it over a full run
    would drop ~1,200 jobs.

    Union by the stable content fingerprint instead. For a posting both sides
    know, keep whichever was seen more recently — that is the run whose data is
    fresher. Postings only one side knows are always kept, which is exactly the
    behaviour that makes an overlap harmless rather than lossy.
    """
    ours_path, base_path = Path(ours_jobs), Path(base_jobs)
    if not base_path.exists():
        return {"merged": 0, "kept_ours": 0, "added_from_base": 0}

    ours = json.loads(ours_path.read_text(encoding="utf-8"))
    base = json.loads(base_path.read_text(encoding="utf-8"))

    def _seen(row: dict) -> str:
        return str(row.get("last_seen_at") or row.get("first_seen_at") or "")

    by_key: dict[str, dict] = {}
    for row in base.get("jobs", []):
        k = row.get("key")
        if k:
            by_key[k] = row
    added_from_base = len(by_key)
    kept_ours = 0
    for row in ours.get("jobs", []):
        k = row.get("key")
        if not k:
            continue
        prev = by_key.get(k)
        if prev is None or _seen(row) >= _seen(prev):
            by_key[k] = row
            kept_ours += 1

    merged = list(by_key.values())
    ours["jobs"] = merged
    ours["count"] = sum(
        1 for r in merged if str(r.get("active_status", "active")).endswith("active")
    )
    # Company tallies must reflect the union, not just this run's slice.
    counts: dict[str, int] = {}
    for r in merged:
        if r.get("is_usa") and str(r.get("active_status", "active")).endswith("active"):
            counts[r.get("company", "")] = counts.get(r.get("company", ""), 0) + 1
    for c in ours.get("companies", []):
        c["usa_active_jobs"] = counts.get(c.get("name", ""), 0)
    ours_path.write_text(json.dumps(ours, separators=(",", ":"), ensure_ascii=False),
                         encoding="utf-8")

    if base_details and ours_details and Path(base_details).exists():
        od = json.loads(Path(ours_details).read_text(encoding="utf-8"))
        bd = json.loads(Path(base_details).read_text(encoding="utf-8"))
        combined = {**bd.get("descriptions", {}), **od.get("descriptions", {})}
        # Drop bodies whose posting is no longer in the corpus.
        live = {str(r.get("id")) for r in merged}
        od["descriptions"] = {k: v for k, v in combined.items() if k in live}
        Path(ours_details).write_text(json.dumps(od, separators=(",", ":"), ensure_ascii=False),
                                      encoding="utf-8")

    report = {"merged": len(merged), "kept_ours": kept_ours,
              "added_from_base": added_from_base, "active": ours["count"]}
    logger.info("merged snapshot: %s", report)
    return report
