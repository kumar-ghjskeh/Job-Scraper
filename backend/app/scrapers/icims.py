"""iCIMS career site scraper using their public JSON feed."""

from __future__ import annotations

import logging
from datetime import datetime

from .base import BaseScraper, JobData

logger = logging.getLogger(__name__)


class ICIMSScraper(BaseScraper):
    """
    iCIMS sites expose a JSON feed at:
      https://careers-{portal}.icims.com/jobs/search?ss=1&searchKeyword={kw}&pr=json
    The portal ID must be set in config as icims_portal.
    """

    async def fetch_jobs(self) -> list[JobData]:
        portal = self.config.get("icims_portal", "")
        if not portal:
            logger.warning("%s: missing icims_portal config", self.company_name)
            return []

        base_url = f"https://careers-{portal}.icims.com/jobs/search"
        keywords = self.config.get("search_keywords", ["verification"])
        jobs: list[JobData] = []
        seen: set[str] = set()

        for kw in keywords[:3]:
            try:
                data = await self._get_json(
                    base_url,
                    params={"ss": "1", "searchKeyword": kw, "pr": "json", "in_iframe": "1"},
                )
            except Exception as e:
                logger.error("iCIMS fetch failed for %s kw=%s: %s", self.company_name, kw, e)
                continue

            for item in data.get("searchResults", []) if isinstance(data, dict) else []:
                job_id = str(item.get("id", ""))
                if job_id in seen:
                    continue
                seen.add(job_id)

                title = item.get("jobtitle", "")
                location = item.get("joblocation", {}).get("city", "") if isinstance(item.get("joblocation"), dict) else ""
                apply_url = item.get("detailUrl", "")

                jobs.append(JobData(
                    job_title=title,
                    apply_url=apply_url,
                    location=location,
                    job_id=job_id,
                    source_url=base_url,
                ))

        return self._filter_relevant(jobs)
