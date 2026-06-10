"""APScheduler setup — runs scrape 4× per day at configured times."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import load_schedule

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _parse_time(t: str) -> tuple[int, int]:
    h, m = t.split(":")
    return int(h), int(m)


def create_scheduler() -> AsyncIOScheduler:
    global _scheduler
    cfg = load_schedule()
    tz = cfg.get("timezone", "America/New_York")
    times: list[str] = cfg.get("scrape_times", ["06:00", "11:30", "15:30", "20:30"])

    _scheduler = AsyncIOScheduler(timezone=tz)

    async def _job():
        from .scrape_engine import run_scrape
        logger.info("Scheduled scrape starting")
        await run_scrape(triggered_by="scheduler")

    for t in times:
        h, m = _parse_time(t)
        _scheduler.add_job(
            _job,
            CronTrigger(hour=h, minute=m, timezone=tz),
            id=f"scrape_{h:02d}{m:02d}",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("Scheduled scrape at %02d:%02d %s", h, m, tz)

    return _scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
