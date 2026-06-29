"""Browser DOM scrapers for big-tech career sites (Apple, Google, Microsoft, Meta).

These sites are JS SPAs whose public APIs are protected/obfuscated, but they
RENDER their job listings into the DOM that a real Chromium session reads
directly — no fragile API or rotating token. Each scraper drives a Playwright
BrowserContext (provided by the browser runner), navigates the public search UI
filtered to the USA + role keywords, and scrapes the rendered cards. Relevance is
gated by ``is_rtl_dv_relevant`` so only genuine RTL/DV roles are kept.

Driven by ``run_browser_scrape`` (local box or the dedicated "giants" GitHub
Actions job with Chromium). Never imported by the Render web service.
"""
from __future__ import annotations

import contextlib
import logging
import re
from datetime import datetime
from typing import Any

from .base import JobData
from ..scoring import is_rtl_dv_relevant

logger = logging.getLogger(__name__)


class BrowserDomScraper:
    """Base for browser DOM scrapers. Subclasses implement ``_search_urls`` and
    ``_extract``. Construct with a Playwright ``BrowserContext``."""

    def __init__(self, company_config: dict, context: Any):
        self.config = company_config
        self.company_name = company_config["name"]
        self._ctx = context

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def fetch_jobs(self) -> list[JobData]:
        seen: dict[str, JobData] = {}
        page = await self._ctx.new_page()
        try:
            for url in self._search_urls():
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(4500)  # let the SPA render the cards
                    rows = await self._extract(page)
                except Exception as e:
                    logger.warning("%s: search page failed (%s): %s",
                                   self.company_name, url[:70], e)
                    continue
                for r in rows:
                    jid = str(r.get("job_id") or r.get("apply_url") or "")
                    if not jid or jid in seen:
                        continue
                    seen[jid] = JobData(
                        job_title=r["title"], apply_url=r["apply_url"],
                        location=r.get("location", "") or "United States", job_id=jid,
                        source_url=r.get("source_url", ""), posted_date=r.get("posted_date"),
                        description_snippet=r.get("snippet", ""),
                        full_description_text=r.get("snippet", ""),
                    )
        finally:
            with contextlib.suppress(Exception):
                await page.close()
        # Strict scraper-side relevance gate — only RTL/DV/ASIC roles survive.
        kept = [j for j in seen.values()
                if is_rtl_dv_relevant(j.job_title, j.full_description_text or "")[0]]
        logger.info("%s: scraped %d cards, %d relevant", self.company_name, len(seen), len(kept))
        return kept

    def _search_urls(self) -> list[str]:
        raise NotImplementedError

    async def _extract(self, page) -> list[dict]:
        raise NotImplementedError


class AppleBrowserScraper(BrowserDomScraper):
    """jobs.apple.com — results filtered to USA in the URL; each card is an
    ``li.rc-accordion-item`` with a ``/details/{id}/`` title link."""

    BASE = "https://jobs.apple.com"

    def _search_urls(self) -> list[str]:
        kws = self.config.get("search_keywords") or ["design verification", "rtl", "asic"]
        urls = []
        for kw in kws:
            q = kw.replace(" ", "%20")
            for pg in (1, 2):
                urls.append(f"{self.BASE}/en-us/search?location=united-states-USA"
                            f"&search={q}&sort=relevance&page={pg}")
        return urls

    async def _extract(self, page) -> list[dict]:
        rows = await page.evaluate(r"""() => {
            const out = [];
            for (const row of document.querySelectorAll('li.rc-accordion-item')) {
                const a = row.querySelector("a[href*='/details/']");
                if (!a) continue;
                const loc = row.querySelector("[id*='location'], .table-col-location");
                out.push({
                    href: a.getAttribute('href'),
                    title: a.textContent.trim(),
                    team: (row.querySelector('.team-name') || {}).textContent || '',
                    posted: (row.querySelector('.job-posted-date') || {}).textContent || '',
                    location: loc ? loc.textContent.replace(/\s+/g, ' ').trim() : '',
                });
            }
            return out;
        }""")
        result = []
        for r in rows:
            href = r.get("href") or ""
            m = re.search(r"/details/([0-9A-Za-z-]+)/", href)
            jid = m.group(1) if m else href
            posted = None
            with contextlib.suppress(Exception):
                posted = datetime.strptime((r.get("posted") or "").strip(), "%b %d, %Y")
            team = (r.get("team") or "").strip()
            # The card's location cell carries a "Location" label prefix — drop it.
            loc = re.sub(r"^\s*Location\b[:\s]*", "", r.get("location", "") or "").strip()
            result.append({
                "job_id": jid,
                "title": r.get("title", ""),
                "apply_url": (self.BASE + href) if href.startswith("/") else href,
                "location": loc,
                "source_url": self.BASE + "/en-us/search",
                "posted_date": posted,
                "snippet": (f"{team} — {r.get('title','')}").strip(" —"),
            })
        return result


def giant_browser_scraper_for(company_config: dict, context: Any):
    """Return a giant browser DOM scraper for the company, or None if its ATS
    isn't a giant handled here."""
    ats = (company_config.get("ats_platform") or "").lower()
    if ats == "apple":
        return AppleBrowserScraper(company_config, context)
    return None
