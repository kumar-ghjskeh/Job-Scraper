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
    r"|api\.smartrecruiters\.com/v1/companies/([a-z0-9]+)/postings"
    # Appended, not inserted: the handler reads groups positionally, so anything
    # added before this point silently renumbers the ones above it.
    # iCIMS is how Arm and Rambus were actually found, and it was missing entirely.
    r"|([a-z0-9-]+)\.icims\.com"
    r"|([a-z0-9-]+)\.avature\.net"
    r"|([a-z0-9-]+)\.eightfold\.ai"
    r"|([a-z0-9-]+)\.my\.site\.com"
    r"|([a-z0-9-]+)\.phenompeople\.com"
    r"|([a-z0-9-]+)\.jobs2web\.com)",
    re.I,
)


# Path segments that are NOT board slugs. jobs.lever.co also serves its static
# assets, so the slug capture happily read "cdn-cgi", "img" and "js" as company
# boards on one candidate. A tool whose output needs manual filtering is a tool
# that will eventually have a wrong board pasted out of it.
NOT_A_SLUG = {
    "cdn-cgi", "img", "images", "js", "css", "static", "assets", "fonts",
    "favicon", "api", "embed", "v0", "v1", "v2", "jobs", "job", "postings",
    "search", "careers", "about", "privacy", "terms", "login", "signup",
}


def looks_related(company: str, slug: str) -> bool:
    """Does this identifier plausibly belong to this company?

    One candidate's page referenced nxp.my.site.com — another company's portal,
    embedded or linked. Reporting that as the candidate's board is the same class
    of error as the greenhouse "ventana" entry that turned out to be a nursing
    home, so anything unrelated is flagged rather than printed as a find.
    """
    import re as _re
    a = _re.sub(r"[^a-z0-9]", "", company.lower())
    b = _re.sub(r"[^a-z0-9]", "", slug.lower())
    if not a or not b:
        return False
    return a[:5] in b or b[:5] in a


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
        elif "icims.com" in u:
            hits.add(("icims", f"{m.group(12)}.icims.com"))
        elif "avature.net" in u:
            hits.add(("avature", m.group(13)))
        elif "eightfold.ai" in u:
            hits.add(("eightfold", m.group(14)))
        elif "my.site.com" in u:
            hits.add(("salesforce(no adapter)", f"{m.group(15)}.my.site.com"))
        elif "phenompeople.com" in u:
            hits.add(("phenom", m.group(16)))
        elif "jobs2web.com" in u:
            hits.add(("jobs2web", m.group(17)))

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
    parts, suspect = [], []
    for ats, slug in sorted(hits):
        bare = slug.split(".")[0]
        if bare in NOT_A_SLUG:
            continue                       # static asset path, not a board
        extra = f"={gh_count(slug)}" if ats == "greenhouse" else ""
        entry = f"{ats}:{slug}{extra}"
        (parts if looks_related(name, bare) else suspect).append(entry)
    if not parts and not suspect:
        return f"XX  {name:24} -> only static-asset paths captured"
    line = f"OK  {name:24} -> " + ", ".join(parts) if parts else f"??  {name:24} ->"
    if suspect:
        line += "   [SUSPECT, name mismatch: " + ", ".join(suspect) + "]"
    return line


def targets_from_config(names: list[str]) -> dict[str, str]:
    """Every company worth probing, read from the catalog rather than hardcoded.

    Default set: entries that are disabled or still on the heuristic `generic`
    adapter — exactly the ones whose real board has not been found yet. The
    hardcoded TARGETS above is kept as a fallback for ad-hoc probing.
    """
    import pathlib

    import yaml
    cfg = pathlib.Path(__file__).resolve().parents[1] / "config" / "companies.yaml"
    companies = yaml.safe_load(cfg.read_text(encoding="utf-8"))["companies"]
    if names:
        wanted = {n.lower() for n in names}
        return {c["name"]: c.get("careers_url", "") for c in companies
                if c["name"].lower() in wanted and c.get("careers_url")}
    return {
        c["name"]: c.get("careers_url", "") for c in companies
        if c.get("careers_url")
        and (not c.get("enabled", True) or c.get("ats_platform") == "generic")
    }


def targets_from_file(path: str) -> dict[str, str]:
    """Candidates NOT yet in the catalog: one `Name,https://careers-url` per line.

    The config-driven mode only sees companies already listed, so this is how a
    fresh candidate sweep is run. Blank lines and `#` comments are ignored.
    """
    import pathlib
    out: dict[str, str] = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "," not in line:
            continue
        name, url = line.split(",", 1)
        out[name.strip()] = url.strip()
    return out


async def main():
    import sys
    args = sys.argv[1:]
    cand = next((a.split("=", 1)[1] for a in args if a.startswith("--candidates=")), None)
    names = [a for a in args if not a.startswith("-")]
    targets = (targets_from_file(cand) if cand
               else targets_from_config(names) or TARGETS)
    print(f"probing {len(targets)} companies", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=UA, locale="en-US", viewport={"width": 1366, "height": 900},
            # Untether AI serves ERR_SSL_VERSION_OR_CIPHER_MISMATCH. Acceptable
            # here: this reads public job listings and sends no credentials.
            ignore_https_errors=True,
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        for name, url in targets.items():
            print(await discover(ctx, name, url), flush=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
