"""Local runner for ``engine: cf`` companies — Cloudflare-walled sites scraped
via curl_cffi (Chrome TLS impersonation). Mirrors the browser runner: it scrapes
each cf company with its registered adapter and persists through the shared
``persist_company_results`` pipeline (identical scoring/dedup as the cloud).

Never imported by the FastAPI web service or the httpx scheduler, so the Render
tier (no curl_cffi needed) is unaffected.

    DATABASE_URL="<prod url>" python -m backend.app.run_cf_scrape
    python -m backend.app.run_cf_scrape --only "Ampere Computing"
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from .config import load_cf_companies, load_schedule
from .scrape_engine import persist_company_results
from .scrapers import get_scraper

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_cf_scrape")


async def main(only: list[str] | None = None) -> None:
    threshold = load_schedule().get("removed_job_threshold", 4)
    companies = load_cf_companies()
    if only:
        wanted = {n.lower() for n in only}
        companies = [c for c in companies if c["name"].lower() in wanted]
    if not companies:
        print("No engine:cf companies matched."); return

    print(f"cf runner: {len(companies)} company(ies)")
    for cfg in companies:
        name = cfg["name"]
        try:
            async with get_scraper(cfg) as sc:
                raw = await sc.fetch_jobs()
            new, removed = await persist_company_results(cfg, raw, threshold)
            print(f"  {name}: fetched={len(raw)} new={new} removed={removed}")
        except Exception as e:
            print(f"  {name}: FAILED {type(e).__name__}: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="Only scrape these company names")
    args = ap.parse_args()
    asyncio.run(main(args.only))
