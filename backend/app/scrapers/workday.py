"""Workday career site scraper using the WD/CXS JSON API."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import BaseScraper, JobData

logger = logging.getLogger(__name__)

# Workday undocumented public REST endpoint pattern
CXS_URL = "https://{tenant}.{instance}.myworkdayjobs.com/wday/cxs/{tenant}/{career_site}/jobs"

# Default search terms for semiconductor / verification roles
DEFAULT_SEARCH_TERMS = ["verification", "rtl design", "asic", "fpga", "digital design"]

LIMIT = 20          # jobs per page
DETAIL_CAP = 80     # max per-job detail fetches per company (descriptions + dates)


def _parse_relative_posted(s: str) -> datetime | None:
    """Workday lists ship a relative string ('Posted Yesterday', 'Posted 30+ Days
    Ago') rather than a date. Convert it to an approximate UTC datetime."""
    if not s:
        return None
    t = s.lower()
    now = datetime.now(timezone.utc)
    if "today" in t or "just posted" in t:
        return now
    if "yesterday" in t:
        return now - timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*day", t)
    if m:
        return now - timedelta(days=int(m.group(1)))
    m = re.search(r"(\d+)\+?\s*week", t)
    if m:
        return now - timedelta(weeks=int(m.group(1)))
    m = re.search(r"(\d+)\+?\s*month", t)
    if m:
        return now - timedelta(days=30 * int(m.group(1)))
    return None


class WorkdayScraper(BaseScraper):
    async def fetch_jobs(self) -> list[JobData]:
        tenant = self.config.get("workday_tenant", "")
        instance = self.config.get("workday_instance", "wd1")
        career_site = self.config.get("workday_career_site", "External")

        if not tenant:
            logger.warning("%s: missing workday_tenant config", self.company_name)
            return []

        base_url = CXS_URL.format(
            tenant=tenant, instance=instance, career_site=career_site
        )

        # Workday rejects requests without a same-origin Origin/Referer with HTTP 422.
        site_root = f"https://{tenant}.{instance}.myworkdayjobs.com"
        self.client.headers.update({
            "Origin": site_root,
            "Referer": f"{site_root}/{career_site}",
            "Sec-Fetch-Site": "same-origin",
        })

        search_terms = self.config.get("search_keywords", DEFAULT_SEARCH_TERMS)
        jobs: list[JobData] = []
        seen_ids: set[str] = set()

        for term in search_terms[:3]:  # limit terms to avoid over-scraping
            fetched = await self._search_workday(base_url, term, seen_ids)
            jobs.extend(fetched)
            await asyncio.sleep(2)

        # Title-first relevance gate, THEN enrich survivors with the per-job detail
        # endpoint (Workday's list omits descriptions and only gives a relative
        # posted string — the detail call returns the full description + a precise
        # startDate).
        relevant = self._filter_relevant(jobs)
        await self._enrich_details(relevant, tenant, instance, career_site)
        return relevant

    async def _enrich_details(self, jobs: list[JobData], tenant: str, instance: str, career_site: str) -> None:
        site_root = f"https://{tenant}.{instance}.myworkdayjobs.com"
        for j in jobs[:DETAIL_CAP]:
            ext_path = j.apply_url[len(site_root):] if j.apply_url.startswith(site_root) else ""
            if not ext_path:
                continue
            try:
                data = await self._get_json(f"{site_root}/wday/cxs/{tenant}/{career_site}{ext_path}")
                info = data.get("jobPostingInfo", {}) if isinstance(data, dict) else {}
                desc = info.get("jobDescription", "") or ""
                if desc:
                    j.full_description_text = desc
                    j.description_snippet = desc[:600]
                start = info.get("startDate", "")
                if start:
                    try:
                        j.posted_date = datetime.fromisoformat(start)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("Workday detail fetch failed %s: %s", j.apply_url, e)
            await asyncio.sleep(0.25)

    async def _search_workday(self, base_url: str, search_text: str, seen_ids: set[str]) -> list[JobData]:
        jobs: list[JobData] = []
        offset = 0

        while True:
            payload = {
                "appliedFacets": {},
                "limit": LIMIT,
                "offset": offset,
                "searchText": search_text,
            }
            try:
                data: Any = await self._post_json(base_url, payload)
            except Exception as e:
                logger.error("Workday fetch failed for %s term=%s: %s", self.company_name, search_text, e)
                break

            items = data.get("jobPostings", [])
            if not items:
                break

            for item in items:
                job_id = item.get("bulletFields", [""])[0] if item.get("bulletFields") else ""
                # Workday uses externalPath for individual job URLs
                ext_path = item.get("externalPath", "")
                job_id = ext_path.split("/")[-1] if ext_path else ""

                if job_id and job_id in seen_ids:
                    continue
                if job_id:
                    seen_ids.add(job_id)

                title = item.get("title", "")
                location = item.get("locationsText", "") or item.get("primaryLocation", "")

                # Build apply URL from external path
                tenant = self.config.get("workday_tenant", "")
                instance = self.config.get("workday_instance", "wd1")
                apply_url = f"https://{tenant}.{instance}.myworkdayjobs.com{ext_path}" if ext_path else ""

                # List ships a relative string ("Posted Yesterday"); parse it as a
                # fallback — _enrich_details will override with the exact startDate.
                posted = _parse_relative_posted(item.get("postedOn", ""))

                jobs.append(
                    JobData(
                        job_title=title,
                        apply_url=apply_url,
                        location=location,
                        job_id=job_id,
                        source_url=base_url,
                        posted_date=posted,
                    )
                )

            total = data.get("total", 0)
            offset += LIMIT
            if offset >= total or offset >= 200:  # cap at 200 results per term
                break
            await asyncio.sleep(1)

        return jobs
