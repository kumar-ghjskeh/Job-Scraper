"""Test whether the existing browser-Workday engine can crack disabled Workday
tenants (Arm, Synopsys, MediaTek, ...). Uses each company's configured
workday_tenant/instance/career_site. Reports relevant RTL/DV count."""
import asyncio
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.config import load_all_companies  # noqa: E402
from backend.app.location_utils import parse_location  # noqa: E402
from backend.app.scrapers.browser import BrowserWorkdayScraper, browser_context  # noqa: E402

TARGETS = sys.argv[1:] or ["Arm"]


async def main():
    companies = {c["name"].lower(): c for c in load_all_companies()}
    async with browser_context(headless=True) as ctx:
        for name in TARGETS:
            cfg = companies.get(name.lower())
            if not cfg:
                print(f"{name}: not found"); continue
            if not cfg.get("workday_tenant"):
                print(f"{name}: no workday_tenant configured (ats={cfg.get('ats_platform')})"); continue
            sc = BrowserWorkdayScraper(cfg, ctx)
            try:
                jobs = await sc.fetch_jobs()
                usa = sum(1 for j in jobs if parse_location(j.location, "").is_usa)
                print(f"[OK]  {name}: tenant={cfg.get('workday_tenant')}/{cfg.get('workday_career_site')} "
                      f"-> relevant={len(jobs)} US={usa}")
                for j in jobs[:5]:
                    print(f"        {j.job_title[:48]:48} | {j.location[:28]}")
            except Exception as e:
                print(f"[FAIL] {name}: {type(e).__name__}: {str(e)[:80]}")


if __name__ == "__main__":
    asyncio.run(main())
