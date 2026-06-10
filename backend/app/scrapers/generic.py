"""Generic scraper: tries httpx first, falls back to Playwright for JS-heavy pages."""

from __future__ import annotations

import asyncio
import logging
import re

from bs4 import BeautifulSoup

from ..config import settings
from .base import BaseScraper, JobData

logger = logging.getLogger(__name__)


class GenericScraper(BaseScraper):
    """
    Fetches the careers_url and attempts to extract job listings from HTML.
    Useful as a fallback for companies without an ATS API.
    Parses common patterns (ul/li links, table rows, div cards).
    """

    async def fetch_jobs(self) -> list[JobData]:
        url = self.config.get("careers_url", "")
        if not url:
            return []

        keywords = self.config.get("search_keywords", [])

        # Try each keyword as a search parameter
        jobs: list[JobData] = []
        seen: set[str] = set()

        for kw in (keywords[:2] or [""]):
            try:
                fetched = await self._fetch_with_keyword(url, kw, seen)
                jobs.extend(fetched)
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning("Generic scrape failed for %s kw=%s: %s", self.company_name, kw, e)

        if not jobs:
            # Try Playwright as last resort
            try:
                jobs = await self._playwright_fetch(url, keywords, seen)
            except Exception as e:
                logger.error("Playwright scrape failed for %s: %s", self.company_name, e)
                raise

        return self._filter_relevant(jobs)

    async def _fetch_with_keyword(self, url: str, keyword: str, seen: set[str]) -> list[JobData]:
        params = {}
        if keyword:
            params["q"] = keyword

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return _parse_html_jobs(resp.text, url, seen)

    async def _playwright_fetch(self, url: str, keywords: list[str], seen: set[str]) -> list[JobData]:
        from playwright.async_api import async_playwright

        jobs: list[JobData] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            html = await page.content()
            await browser.close()

        jobs.extend(_parse_html_jobs(html, url, seen))
        return jobs


def _parse_html_jobs(html: str, source_url: str, seen: set[str]) -> list[JobData]:
    """Heuristic HTML parser — looks for job-card-like structures."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[JobData] = []

    # Strategy 1: look for <li> or <div> containing a link with job-like text
    job_keywords = re.compile(
        r"(verification|rtl|asic|fpga|digital design|logic design|silicon|soc|cpu|gpu|dv|uvm)",
        re.I,
    )

    for tag in soup.find_all(["li", "article", "div"], limit=300):
        a_tags = tag.find_all("a", href=True, recursive=False) or tag.find_all("a", href=True)
        for a in a_tags[:1]:
            title = a.get_text(strip=True)
            if len(title) < 8 or not job_keywords.search(title):
                continue
            href = a.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)

            # Resolve relative URLs
            if href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(source_url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"

            # Look for location text nearby
            location = ""
            parent = tag.parent
            if parent:
                loc_span = parent.find(string=re.compile(r"\b(CA|TX|WA|NY|MA|Remote|United States)\b"))
                if loc_span:
                    location = str(loc_span).strip()

            jobs.append(JobData(
                job_title=title,
                apply_url=href,
                location=location,
                source_url=source_url,
            ))

    return jobs
