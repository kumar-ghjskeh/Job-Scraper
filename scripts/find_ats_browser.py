"""Browser-rendered ATS discovery. JS-heavy careers pages only reveal their ATS
board after scripts run, so load each in real Chromium and capture the network
calls to Greenhouse / Lever / Ashby / Workday / SmartRecruiters — those URLs
contain the exact board slug. Prints a paste-ready summary per company.
"""
import asyncio
import json
import re
import ssl
import urllib.request

from playwright.async_api import async_playwright

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")

TARGETS = {
    "Groq": "https://groq.com/careers/",
    "Arista Networks": "https://www.arista.com/en/careers",
    "Synaptics": "https://www.synaptics.com/careers",
    "Achronix": "https://www.achronix.com/careers",
    "Alphawave Semi": "https://awaveip.com/careers/",
    "Credo Semiconductor": "https://www.credosemi.com/careers/",
    "Cornelis Networks": "https://www.cornelisnetworks.com/careers/",
    "Enfabrica": "https://www.enfabrica.net/",
    "Esperanto Technologies": "https://www.esperanto.ai/careers/",
    "MaxLinear": "https://www.maxlinear.com/company/careers",
    "Untether AI": "https://www.untether.ai/",
    "Ayar Labs": "https://ayarlabs.com/careers/",
    "Rivos": "https://rivosinc.com/careers/",
    "SiMa.ai": "https://sima.ai/careers/",
    "Recogni": "https://recogni.com/careers/",
    "Celestial AI": "https://www.celestial.ai/careers",
    "Mythic": "https://mythic.ai/careers/",
    "Blaize": "https://www.blaize.com/careers/",
    "Quadric": "https://quadric.io/careers/",
    "Expedera": "https://www.expedera.com/careers/",
}

CAPTURE = re.compile(
    r"(boards-api\.greenhouse\.io/v1/boards/([a-z0-9]+)"
    r"|job-?boards\.greenhouse\.io/([a-z0-9]+)"
    r"|api\.lever\.co/v0/postings/([a-z0-9-]+)"
    r"|jobs\.lever\.co/([a-z0-9-]+)"
    r"|api\.ashbyhq\.com/posting-api/job-board/([a-z0-9-]+)"
    r"|jobs\.ashbyhq\.com/([a-z0-9-]+)"
    r"|([a-z0-9]+)\.(wd\d)\.myworkdayjobs\.com/(?:wday/cxs/[a-z0-9]+/)?([A-Za-z0-9_-]+)"
    r"|api\.smartrecruiters\.com/v1/companies/([a-z0-9]+)/postings)",
    re.I,
)


def gh_count(slug):
    try:
        req = urllib.request.Request(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            return len(json.loads(r.read()).get("jobs", []))
    except Exception:
        return "?"


async def discover(ctx, name, url):
    page = await ctx.new_page()
    hits = set()

    def on_request(req):
        m = CAPTURE.search(req.url)
        if not m:
            return
        u = req.url
        if "greenhouse" in u:
            slug = m.group(2) or m.group(3)
            if slug and slug not in ("embed",):
                hits.add(("greenhouse", slug))
        elif "lever.co" in u:
            slug = m.group(4) or m.group(5)
            if slug:
                hits.add(("lever", slug))
        elif "ashbyhq" in u:
            slug = m.group(6) or m.group(7)
            if slug and slug not in ("api",):
                hits.add(("ashby", slug))
        elif "myworkdayjobs" in u:
            hits.add(("workday", f"{m.group(8)}.{m.group(9)}/{m.group(10)}"))
        elif "smartrecruiters" in u:
            hits.add(("smartrecruiters", m.group(11)))

    page.on("request", on_request)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        try:
            await page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            pass
        await page.wait_for_timeout(3500)
    except Exception as e:
        await page.close()
        return f"XX  {name:24} nav-error {str(e)[:40]}"
    await page.close()

    if not hits:
        return f"XX  {name:24} -> no ATS calls captured"
    parts = []
    for ats, slug in sorted(hits):
        extra = f"={gh_count(slug)}" if ats == "greenhouse" else ""
        parts.append(f"{ats}:{slug}{extra}")
    return f"OK  {name:24} -> " + ", ".join(parts)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="en-US",
                                        viewport={"width": 1366, "height": 900})
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        for name, url in TARGETS.items():
            print(await discover(ctx, name, url), flush=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
