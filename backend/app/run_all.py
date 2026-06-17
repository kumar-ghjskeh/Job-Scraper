"""Run every browserless scrape engine once against the configured DATABASE_URL:
the httpx scheduler pass (clean-API companies) + the curl_cffi pass (anti-bot
Workday/Eightfold/Jobvite/Avature/Radancy/Cloudflare companies).

Entry point for the free 24/7 GitHub Actions schedule — needs only httpx +
curl_cffi (no Chromium). Independent of any local machine.

    DATABASE_URL="<prod url>" python -m backend.app.run_all
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_all")


def _require_prod_db() -> None:
    """Fail fast with a readable message if the production DB URL is missing.

    On GitHub Actions an unset ``DATABASE_URL`` secret is injected as an empty
    string, which would otherwise blow up cryptically inside SQLAlchemy at import
    time. Catch it here so the failure says exactly what to fix."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url or url.startswith("sqlite"):
        logger.error(
            "DATABASE_URL is not set to the production Postgres URL. "
            "Add it as a GitHub repo secret: Settings -> Secrets and variables -> "
            "Actions -> New repository secret, name DATABASE_URL = the Render "
            "External Postgres connection string. (got: %r)", url or "<empty>")
        sys.exit(78)  # EX_CONFIG — clearly a configuration problem, not a code bug


async def _run() -> None:
    # Imported here (after the DB check) so an empty DATABASE_URL doesn't crash at
    # import time inside database.create_engine().
    from .database import init_db
    from .run_cf_scrape import main as cf_main
    from .scrape_engine import run_scrape

    init_db()
    logger.info("=== httpx pass (clean-API companies) ===")
    try:
        run = await run_scrape(triggered_by="github-actions")
        logger.info("httpx pass: companies=%s new=%s removed=%s errors=%s",
                    run.companies_scraped, run.new_jobs, run.removed_jobs, run.errors)
    except Exception as e:
        logger.error("httpx pass FAILED: %s", e)

    logger.info("=== curl_cffi pass (anti-bot companies) ===")
    try:
        await cf_main()
    except Exception as e:
        logger.error("curl_cffi pass FAILED: %s", e)

    logger.info("=== run_all complete ===")


def main() -> None:
    _require_prod_db()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
