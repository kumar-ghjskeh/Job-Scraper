"""Real-browser engine wiring: the engine:browser companies must stay isolated
from the httpx scheduler, and BrowserWorkdayScraper must route every HTTP call
through the injected Playwright context (never httpx). No network / no Chromium
is used here — the browser context is faked."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

import asyncio
import json

from backend.app.config import load_cf_companies, load_companies
from backend.app.scrapers.browser import BrowserWorkdayScraper
from backend.app.scrapers.avature import AvatureScraper
from backend.app.scrapers.cf import CfEightfoldScraper, CfWorkdayScraper, cf_scraper_for
from backend.app.scrapers.jobvite import JobviteScraper
from backend.app.scrapers.radancy import RadancyScraper


def test_cf_companies_isolated_from_httpx_scheduler():
    """Anti-bot companies are scraped by the curl_cffi engine (engine:cf) and
    must never appear in the enabled set the httpx scheduler iterates (or they'd
    hit the anti-bot / Cloudflare wall and error out)."""
    cf = load_cf_companies()
    assert cf, "expected at least one engine:cf company"

    httpx_names = {c["name"] for c in load_companies()}
    for c in cf:
        assert c.get("engine") == "cf"
        assert c["name"] not in httpx_names, f"{c['name']} leaks into httpx scheduler"
        ats = c.get("ats_platform")
        if ats == "workday":
            assert c.get("workday_tenant") and c.get("workday_career_site")
            assert isinstance(cf_scraper_for(c), CfWorkdayScraper)
        elif ats == "eightfold":
            assert c.get("eightfold_tenant") and c.get("eightfold_domain")
            assert isinstance(cf_scraper_for(c), CfEightfoldScraper)
        elif ats == "jobvite":
            assert c.get("jobvite_host")
            assert isinstance(cf_scraper_for(c), JobviteScraper)
        elif ats == "avature":
            assert c.get("avature_host")
            assert isinstance(cf_scraper_for(c), AvatureScraper)
        elif ats == "radancy":
            assert c.get("radancy_host")
            assert isinstance(cf_scraper_for(c), RadancyScraper)
        else:
            raise AssertionError(f"{c['name']}: unexpected cf ats {ats!r}")


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.ok = True
        self.status = 200

    async def json(self):
        return self._payload


class _FakeRequest:
    """Records calls so the test can assert the scraper used the browser session."""

    def __init__(self):
        self.posts = []
        self.gets = []

    async def post(self, url, data=None, headers=None, timeout=None):
        self.posts.append((url, json.loads(data) if data else None))
        return _FakeResponse({"jobPostings": [], "total": 0})

    async def get(self, url, headers=None, timeout=None):
        self.gets.append(url)
        return _FakeResponse({"jobPostingInfo": {}})


class _FakeContext:
    def __init__(self):
        self.request = _FakeRequest()


def test_browser_scraper_routes_http_through_context():
    cfg = {
        "name": "Cadence Design Systems", "ats_platform": "workday",
        "workday_tenant": "cadence", "workday_instance": "wd1",
        "workday_career_site": "External_Careers",
    }
    ctx = _FakeContext()
    scraper = BrowserWorkdayScraper(cfg, ctx)

    async def go():
        out = await scraper._post_json("https://x/wday/cxs/cadence/External_Careers/jobs",
                                       {"searchText": "rtl", "limit": 20, "offset": 0})
        await scraper._get_json("https://x/wday/cxs/cadence/External_Careers/job/abc")
        return out

    result = asyncio.run(go())
    # Routed through the fake browser context, not httpx:
    assert ctx.request.posts and ctx.request.posts[0][1]["searchText"] == "rtl"
    assert ctx.request.gets
    assert result == {"jobPostings": [], "total": 0}
    # Workday same-origin headers are attached so the CXS call is accepted
    assert scraper._wd_headers()["Origin"] == "https://cadence.wd1.myworkdayjobs.com"
