"""Abstract base scraper with shared HTTP utilities."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": settings.scraper_user_agent,
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


class JobData:
    """Raw job data returned by scrapers before DB persistence."""

    __slots__ = (
        "job_id", "job_title", "location", "apply_url", "source_url",
        "posted_date", "description_snippet", "full_description_text",
    )

    def __init__(
        self,
        job_title: str,
        apply_url: str,
        location: str = "",
        job_id: str = "",
        source_url: str = "",
        posted_date: Any = None,
        description_snippet: str = "",
        full_description_text: str = "",
    ):
        self.job_title = job_title
        self.apply_url = apply_url
        self.location = location
        self.job_id = job_id
        self.source_url = source_url
        self.posted_date = posted_date
        self.description_snippet = description_snippet
        self.full_description_text = full_description_text


class BaseScraper(ABC):
    def __init__(self, company_config: dict):
        self.config = company_config
        self.company_name: str = company_config["name"]
        self.client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.client.aclose()

    @abstractmethod
    async def fetch_jobs(self) -> list[JobData]:
        """Return list of raw JobData objects for this company."""

    async def _get_json(self, url: str, **kwargs) -> Any:
        await asyncio.sleep(settings.request_timeout_seconds * 0)  # yield
        resp = await self.client.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _post_json(self, url: str, payload: dict, **kwargs) -> Any:
        resp = await self.client.post(url, json=payload, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _keywords_match(self, text: str, keywords: list[str]) -> bool:
        text_l = text.lower()
        return any(kw.lower() in text_l for kw in keywords)

    def _filter_relevant(self, jobs: list[JobData]) -> list[JobData]:
        """Keep only genuine RTL Design / Design Verification (or adjacent
        silicon) roles. Uses a precise title-first relevance gate so the stored
        job pool is unambiguous — no software/sales/HR noise."""
        from ..scoring import is_rtl_dv_relevant

        relevant: list[JobData] = []
        for j in jobs:
            ok, _reason = is_rtl_dv_relevant(
                j.job_title, j.description_snippet or j.full_description_text or ""
            )
            if ok:
                relevant.append(j)
        return relevant
