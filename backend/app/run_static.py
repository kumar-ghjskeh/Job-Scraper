"""Scrape with no hosted database anywhere — the static-snapshot pipeline.

Each run is self-contained:

    1. build a scratch SQLite database in the runner's temp dir
    2. seed it from the committed snapshot (frontend/public/data/jobs.json)
    3. run the normal scrape engine against it — unchanged code, same scrapers,
       same relevance/location/dedupe logic, so results are identical
    4. write a fresh snapshot back out

Nothing persists between runs except two JSON files in the repo, which diff and
compress well. There is no connection to meter, no transfer quota to exhaust and
no service to keep awake — the failure mode that took this app down three times
cannot occur because the component is gone.

    DATA_DIR=frontend/public/data python -m backend.app.run_static
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_static")

DATA_DIR = Path(os.getenv("DATA_DIR", "frontend/public/data"))


def _use_scratch_db() -> Path:
    """Point the app at a throwaway SQLite file BEFORE app.database is imported."""
    scratch = Path(os.getenv("RUNNER_TEMP", tempfile.gettempdir())) / "ashborne_scrape.db"
    if scratch.exists():
        scratch.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{scratch.as_posix()}"
    return scratch


async def _run() -> int:
    from .database import init_db
    from .run_cf_scrape import main as cf_main
    from .scrape_engine import run_scrape, sweep_stale_jobs
    from .snapshot import load_snapshot_into_db, write_snapshot

    init_db()
    restored = load_snapshot_into_db(DATA_DIR / "jobs.json", DATA_DIR / "details.json")
    logger.info("seeded scratch database with %d job(s) from the last snapshot", restored)

    failures: list[str] = []
    scraped_ok = False

    logger.info("=== httpx pass ===")
    try:
        run = await run_scrape(triggered_by="static")
        logger.info("httpx pass: companies=%s new=%s removed=%s errors=%s",
                    run.companies_scraped, run.new_jobs, run.removed_jobs, run.errors)
        if not run.companies_scraped:
            raise RuntimeError("httpx pass scraped 0 companies")
        scraped_ok = True
    except Exception as e:
        logger.exception("httpx pass FAILED")
        failures.append(f"httpx: {e}")

    logger.info("=== curl_cffi pass ===")
    try:
        await cf_main()
        scraped_ok = True
    except Exception as e:
        logger.exception("curl_cffi pass FAILED")
        failures.append(f"curl_cffi: {e}")

    if scraped_ok:
        try:
            logger.info("stale sweep retired %s job(s)", sweep_stale_jobs())
        except Exception as e:
            logger.error("stale sweep FAILED: %s", e)
    else:
        logger.warning("stale sweep SKIPPED — no pass succeeded")

    # Only publish when something actually scraped. Writing a snapshot after a
    # total failure would replace good data with an empty corpus — the static
    # design's one genuine footgun, so it is guarded here.
    if not scraped_ok:
        logger.error("NOT writing a snapshot — no scrape pass succeeded; "
                     "the previous snapshot stays live")
        raise RuntimeError("; ".join(failures))

    report = write_snapshot(DATA_DIR)
    logger.info("snapshot written to %s: %s jobs", DATA_DIR, report["count"])
    if failures:
        raise RuntimeError("; ".join(failures))
    return report["count"]


def main() -> None:
    _use_scratch_db()
    count = asyncio.run(_run())
    if count == 0:
        logger.error("snapshot contains 0 jobs — refusing to call this a success")
        sys.exit(1)


if __name__ == "__main__":
    main()
