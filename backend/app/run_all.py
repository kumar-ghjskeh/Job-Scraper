"""Run every browserless scrape engine once against the configured DATABASE_URL:
the httpx scheduler pass (clean-API companies) + the curl_cffi pass (anti-bot
Workday/Eightfold/Jobvite/Cloudflare companies).

This is the entry point for the free 24/7 GitHub Actions schedule — it needs only
httpx + curl_cffi (no Chromium), so it runs in a couple of minutes on a tiny CI
box, independent of any local machine. Each engine is isolated so one failing
pass never aborts the other.

    DATABASE_URL="<prod url>" python -m backend.app.run_all
"""
from __future__ import annotations

import asyncio
import logging

from .database import init_db
from .run_cf_scrape import main as cf_main
from .scrape_engine import run_scrape

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_all")


async def main() -> None:
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


if __name__ == "__main__":
    asyncio.run(main())
