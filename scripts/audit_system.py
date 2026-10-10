"""Check the invariants this system has actually broken before.

Not a test suite — a standing audit of the LIVE corpus and config, written because
the same few classes of bug keep recurring and each one was invisible until it
reached CI:

  * a field added to the export but not to the restore path (removed_at killed every
    scrape for three runs)
  * the publishing pass overwriting data it never scraped (company tallies, run
    history, and health counters, three separate times)
  * a hidden-category set drifting between the four places that decide what shows
  * a classification that silently resolves to "unknown" and drops rows from a view

    py scripts/audit_system.py            # audit the committed corpus
    py scripts/audit_system.py --strict   # exit 1 on any WARN as well as FAIL

Exits non-zero on FAIL so it can gate a workflow.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys
from datetime import datetime, timezone

# Windows consoles default to cp1252 and this output has box-drawing characters.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []
WARNS: list[str] = []
PASSES: list[str] = []


def ok(msg: str) -> None:
    PASSES.append(msg)


def warn(msg: str) -> None:
    WARNS.append(msg)


def fail(msg: str) -> None:
    FAILS.append(msg)


def section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 68 - len(title)))


def load_corpus() -> dict:
    p = ROOT / "frontend" / "public" / "data" / "jobs.json"
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


# ── 1. Export/restore symmetry ────────────────────────────────────────────────
def check_export_restore_symmetry() -> None:
    section("export / restore symmetry")
    from sqlalchemy import Date, DateTime

    from backend.app.models import JobPosting, UtcDateTime
    from backend.app.snapshot import (
        _EXPORTED_DATETIME_FIELDS,
        LIST_FIELDS,
        RETIRED_ROW_FIELDS,
    )

    cols = {c.name: c for c in JobPosting.__table__.columns}  # type: ignore[attr-defined]

    # Every exported datetime column must be coerced back on restore. This is the
    # removed_at outage, generalised.
    dt_exported = {
        n for n, c in cols.items()
        if n in LIST_FIELDS and isinstance(c.type, (UtcDateTime, DateTime, Date))
    }
    if not dt_exported:
        fail("no exported datetime columns detected — the derivation matches nothing")
    missing = dt_exported - set(_EXPORTED_DATETIME_FIELDS)
    if missing:
        fail(f"exported datetime columns not coerced on restore: {sorted(missing)}")
    else:
        ok(f"all {len(dt_exported)} exported datetime columns are coerced on restore")

    # Every exported field should be a real column (or a known derived extra).
    # Model @property values that LIST_FIELDS picks up via getattr, plus the
    # fingerprint added at export time. Not columns, not bugs.
    DERIVED = {"key", "sponsors_h1b", "display_location"}
    unknown = [f for f in LIST_FIELDS if f not in cols and f not in DERIVED]
    if unknown:
        warn(f"LIST_FIELDS names that are neither columns nor known derived: {unknown}")
    else:
        ok("every LIST_FIELDS entry is a column or a known derived field")

    # A retired row must keep everything the removal machine and merge read.
    need = {"key", "company", "job_title", "apply_url", "job_id_from_company",
            "active_status", "missed_scrapes", "last_seen_at", "removed_at"}
    gap = need - set(RETIRED_ROW_FIELDS)
    if gap:
        fail(f"RETIRED_ROW_FIELDS is missing load-bearing fields: {sorted(gap)}")
    else:
        ok("retired rows keep every field the removal machine and merge need")


# ── 2. Corpus data integrity ──────────────────────────────────────────────────
def check_corpus(d: dict) -> None:
    section("corpus data integrity")
    from backend.app.models import ActiveStatus, RoleCategory
    from backend.app.snapshot import RETIRED_ROW_FIELDS

    jobs = d.get("jobs") or []
    if not jobs:
        fail("corpus has no jobs at all")
        return
    ok(f"{len(jobs)} rows in the corpus")

    valid_status = {s.value for s in ActiveStatus}
    bad_status = {j.get("active_status") for j in jobs} - valid_status - {None}
    if bad_status:
        fail(f"unknown active_status values: {sorted(bad_status)}")
    else:
        ok(f"all active_status values are valid: {sorted(valid_status & {j.get('active_status') for j in jobs})}")

    active = [j for j in jobs if (j.get("active_status") or "active") == "active"]
    retired = [j for j in jobs if (j.get("active_status") or "active") != "active"]

    # Retired rows must be stripped — otherwise the payload silently re-inflates.
    fat = [j for j in retired if set(j) - set(RETIRED_ROW_FIELDS)]
    if fat:
        fail(f"{len(fat)} retired rows carry fields outside RETIRED_ROW_FIELDS "
             f"(payload re-inflated); e.g. {sorted(set(fat[0]) - set(RETIRED_ROW_FIELDS))[:6]}")
    else:
        ok(f"all {len(retired)} retired rows are stripped to the minimum")

    # Required fields on anything we might show.
    for field in ("company", "job_title", "apply_url", "key"):
        nulls = [j for j in active if not j.get(field)]
        if nulls:
            fail(f"{len(nulls)} active rows have no {field}")
    if not any(not j.get(f) for j in active for f in ("company", "job_title", "apply_url", "key")):
        ok("every active row has company, job_title, apply_url and key")

    # Timestamps must parse and be timezone-aware — the nine-day-outage class.
    naive, unparseable = [], []
    for j in jobs:
        for f in ("posted_date", "first_seen_at", "last_seen_at", "removed_at"):
            v = j.get(f)
            if not v:
                continue
            try:
                parsed = datetime.fromisoformat(str(v))
            except ValueError:
                unparseable.append((f, v))
                continue
            if parsed.tzinfo is None:
                naive.append((f, v))
    if unparseable:
        fail(f"{len(unparseable)} timestamps do not parse, e.g. {unparseable[:2]}")
    elif naive:
        fail(f"{len(naive)} timestamps are timezone-NAIVE, e.g. {naive[:2]}")
    else:
        ok("every timestamp parses and carries a timezone")

    # role_category must be a value the UI knows about.
    known = {c.value for c in RoleCategory} | {"Software / Compiler"}
    seen = {j.get("role_category") for j in active if j.get("role_category")}
    unknown_cats = seen - known
    if unknown_cats:
        fail(f"active rows use role_category values the model does not define: {sorted(unknown_cats)}")
    else:
        ok(f"all {len(seen)} role_category values in use are model-defined")

    # Duplicate fingerprints would make the merge drop rows.
    keys = [j.get("key") for j in jobs if j.get("key")]
    dupes = [k for k, n in collections.Counter(keys).items() if n > 1]
    if dupes:
        fail(f"{len(dupes)} duplicate fingerprints — the merge keeps only one of each")
    else:
        ok("every fingerprint is unique")

    # A US row with no country, or a non-US row claiming a US state.
    bad_loc = [j for j in active if j.get("is_usa") and not (j.get("country") or j.get("state") or j.get("is_remote_usa"))]
    if bad_loc:
        warn(f"{len(bad_loc)} active rows are flagged is_usa with no country, state or remote marker")
    else:
        ok("US-flagged rows all carry a country, state or remote marker")


# ── 3. What the board actually shows ──────────────────────────────────────────
def check_visible_scope(d: dict) -> None:
    section("visible scope (RTL design + DV only)")
    from backend.app.role_scope import classify_scope
    from backend.app.snapshot import HIDDEN_CATEGORIES

    vis = [
        j for j in d["jobs"]
        if (j.get("active_status") or "active") == "active"
        and j.get("is_usa")
        and not j.get("is_software_only")
        and j.get("role_category") not in HIDDEN_CATEGORIES
    ]
    ok(f"{len(vis)} visible US jobs")

    leaks = [j for j in vis if not classify_scope(j.get("job_title") or "")[0]]
    if leaks:
        fail(f"{len(leaks)} visible jobs are NOT RTL design or DV by the scope gate, "
             f"e.g. {[j['job_title'][:44] for j in leaks[:3]]}")
    else:
        ok("every visible job passes the strict RTL/DV scope gate")

    # The inverse: in-scope rows that are hidden anyway.
    hidden_in_scope = [
        j for j in d["jobs"]
        if (j.get("active_status") or "active") == "active" and j.get("is_usa")
        and j.get("role_category") in HIDDEN_CATEGORIES
        and classify_scope(j.get("job_title") or "")[0]
        and not j.get("is_software_only")
    ]
    if hidden_in_scope:
        warn(f"{len(hidden_in_scope)} rows pass the scope gate but sit in a hidden "
             f"category, e.g. {[(j['job_title'][:34], j['role_category']) for j in hidden_in_scope[:3]]}")
    else:
        ok("no in-scope job is stuck in a hidden category")


# ── 4. The four places that must agree on what is hidden ──────────────────────
def check_hidden_set_agreement() -> None:
    section("hidden-category agreement across all four deciders")
    import inspect

    from backend.app import main
    from backend.app.snapshot import HIDDEN_CATEGORIES

    if "tuple(HIDDEN_CATEGORIES)" not in inspect.getsource(main):
        fail("backend/app/main.py no longer shares HIDDEN_CATEGORIES (hardcoded copy will drift)")
    else:
        ok("main.py shares the backend hidden set")

    for rel in ("frontend/src/lib/query.ts", "frontend/src/lib/corpus.ts"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        gap = [c for c in HIDDEN_CATEGORIES if f"'{c}'" not in text]
        if gap:
            fail(f"{rel} does not hide {gap}")
        else:
            ok(f"{rel} hides all {len(HIDDEN_CATEGORIES)} categories")


# ── 5. Company config and directory ───────────────────────────────────────────
def check_companies(d: dict) -> None:
    section("company config and directory")
    import yaml

    from backend.app.eligibility import sponsors_h1b

    cfg = yaml.safe_load((ROOT / "config" / "companies.yaml").read_text(encoding="utf-8"))
    companies = cfg["companies"]
    ok(f"{len(companies)} companies in config, {sum(1 for c in companies if c.get('enabled', True))} enabled")

    names = [c["name"] for c in companies]
    dupes = [n for n, k in collections.Counter(names).items() if k > 1]
    if dupes:
        fail(f"duplicate company names: {dupes}")
    else:
        ok("no duplicate company names")

    nourl = [c["name"] for c in companies if not c.get("careers_url")]
    if nourl:
        fail(f"companies with no careers_url: {nourl}")
    else:
        ok("every company has a careers_url")

    unclassified = [c["name"] for c in companies if sponsors_h1b(c["name"]) is None]
    if unclassified:
        fail(f"companies with no H1B classification (they vanish from the H1B view): {unclassified}")
    else:
        ok("every company is classified for H1B sponsorship")

    # Enabled API companies must declare their slug explicitly.
    SLUG = {"greenhouse": "greenhouse_board", "ashby": "ashby_org",
            "lever": "lever_company", "smartrecruiters": "smartrecruiters_company"}
    noslug = [
        c["name"] for c in companies
        if c.get("enabled", True)
        and (f := SLUG.get((c.get("ats_platform") or "").lower()))
        and not c.get(f)
    ]
    if noslug:
        fail(f"enabled API companies with no explicit slug: {noslug}")
    else:
        ok("every enabled API company declares its slug")

    # The directory in the published corpus must match the config.
    published = {c["name"] for c in d.get("companies", [])}
    drift = set(names) ^ published
    if drift:
        warn(f"{len(drift)} companies differ between config and the published "
             f"directory (a re-export is pending): {sorted(drift)[:5]}")
    else:
        ok("the published directory matches the config exactly")


# ── 6. Per-company health signals ─────────────────────────────────────────────
def check_health(d: dict) -> None:
    section("source health signals")
    rows = d.get("companies") or []
    spread = collections.Counter(c.get("scrape_status") for c in rows)
    ok(f"status spread: {dict(spread)}")

    # A company reporting jobs must not also read as broken.
    contradictory = [
        c["name"] for c in rows
        if (c.get("total_active_jobs") or 0) > 0 and c.get("scrape_status") in ("stalled", "quarantined")
    ]
    if contradictory:
        fail(f"companies producing jobs but flagged broken: {contradictory}")
    else:
        ok("no company both produces jobs and reads as broken")

    # auto_connected must follow from actually having postings.
    bad = [c["name"] for c in rows
           if bool(c.get("auto_connected")) != ((c.get("total_active_jobs") or 0) > 0)]
    if bad:
        fail(f"auto_connected disagrees with total_active_jobs for: {bad[:6]}")
    else:
        ok("auto_connected agrees with the job counts everywhere")

    flagged = [c for c in rows if c.get("scrape_status") in ("stalled", "quarantined", "error")]
    if flagged:
        warn(f"{len(flagged)} sources need attention: " +
             ", ".join(f"{c['name']}({c['scrape_status']})" for c in flagged))
    else:
        ok("no source is flagged")


# ── 7. Freshness and ranking inputs ───────────────────────────────────────────
def check_freshness(d: dict) -> None:
    section("freshness and ranking inputs")
    from backend.app.snapshot import HIDDEN_CATEGORIES

    now = datetime.now(timezone.utc)
    vis = [
        j for j in d["jobs"]
        if (j.get("active_status") or "active") == "active" and j.get("is_usa")
        and not j.get("is_software_only")
        and j.get("role_category") not in HIDDEN_CATEGORIES
    ]
    if not vis:
        fail("nothing visible at all")
        return

    noscore = [j for j in vis if j.get("new_grad_fit") is None]
    if noscore:
        warn(f"{len(noscore)} visible jobs have no new_grad_fit, so the default sort "
             "cannot rank them")
    else:
        ok("every visible job carries a new_grad_fit score")

    # first_seen_at clustering: a bulk-import baseline the UI must not present as a
    # discovery date.
    by_day = collections.Counter(str(j.get("first_seen_at") or "")[:10] for j in d["jobs"]
                                 if (j.get("active_status") or "active") == "active")
    if by_day:
        day, n = by_day.most_common(1)[0]
        share = n / sum(by_day.values())
        if share >= 0.25:
            earliest = min(k for k in by_day if k)
            label = "import baseline (handled)" if day == earliest else "UNEXPECTED spike"
            (ok if day == earliest else warn)(
                f"{share:.0%} of active rows share first_seen_at {day} — {label}")
        else:
            ok("no first_seen_at date dominates the corpus")

    ages = []
    for j in vis:
        raw = (j.get("posted_date") if j.get("posted_date_known") else None) or j.get("first_seen_at")
        try:
            ages.append((now - datetime.fromisoformat(str(raw))).days)
        except (TypeError, ValueError):
            pass
    if ages:
        ages.sort()
        med = ages[len(ages) // 2]
        fresh = sum(1 for a in ages if a <= 7)
        ok(f"median visible age {med} days; {fresh} ({fresh / len(ages):.0%}) within a week")
        if med > 60:
            warn(f"median visible age is {med} days — retirement may not be draining")


def check_frontend_builds() -> None:
    """The gate that was missing.

    `tsc --noEmit` passed while `tsc -b` — which is what `npm run build` and therefore
    Vercel runs — failed on a single missing comma in the machine-appended DOMAINS
    literal. Nothing deployed for two hours while data commits piled up, and the live
    site served a two-hour-old corpus. Checking types is not checking the build.
    """
    section("frontend build")
    import re as _re
    import subprocess

    fe = ROOT / "frontend"
    src = (fe / "src" / "components" / "CompanyLogo.tsx").read_text(encoding="utf-8")

    # Cheap structural check first, aimed at exactly the shape that broke: DOMAINS is
    # appended to by script, and batch 2 appended after an entry whose trailing comma
    # had been stripped as "last".
    m = _re.search(r"const DOMAINS: Record<string, string> = \{(.*?)\n\}", src, _re.S)
    if not m:
        fail("could not find the DOMAINS literal in CompanyLogo.tsx")
    else:
        bad = [
            line for line in m.group(1).strip().splitlines()
            if line.strip()
            and not line.strip().startswith("//")
            and not line.rstrip().endswith(",")
        ]
        if bad:
            fail("DOMAINS entries with no trailing comma — a later append will break "
                 f"the object literal and fail the build: {bad}")
        else:
            ok("every DOMAINS entry ends with a comma, so appending stays safe")

    if "--no-build" in sys.argv:
        warn("skipped the frontend build (--no-build)")
        return
    try:
        r = subprocess.run(["npm", "run", "build"], cwd=fe, capture_output=True,
                           text=True, timeout=300, shell=True)
    except Exception as e:
        warn(f"could not run the frontend build: {type(e).__name__}: {e}")
        return
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()[-5:]
        fail("the frontend BUILD fails, so Vercel will not deploy: " + " | ".join(tail))
    else:
        ok("the frontend builds (tsc -b + vite build), so Vercel can deploy")


def main() -> int:
    strict = "--strict" in sys.argv
    print("Ashborne Silicon — system audit")
    d = load_corpus()
    print(f"corpus generated {d.get('generated_at', '?')[:19]}")

    for fn, arg in (
        (check_export_restore_symmetry, None),
        (check_corpus, d),
        (check_visible_scope, d),
        (check_hidden_set_agreement, None),
        (check_companies, d),
        (check_health, d),
        (check_freshness, d),
        (check_frontend_builds, None),
    ):
        try:
            fn(d) if arg is not None else fn()
        except Exception as e:  # an audit that crashes tells you nothing
            fail(f"{fn.__name__} crashed: {type(e).__name__}: {e}")
        for m in PASSES:
            print(f"  PASS  {m}")
        for m in WARNS:
            print(f"  WARN  {m}")
        for m in FAILS:
            print(f"  FAIL  {m}")
        PASSES.clear()
        WARNS.clear()
        FAILS.clear()

    return 0


if __name__ == "__main__":
    # Collect across sections for the summary rather than clearing silently.
    import io as _io

    buf = _io.StringIO()
    real = sys.stdout
    sys.stdout = buf
    main()
    sys.stdout = real
    out = buf.getvalue()
    print(out)
    n_fail = out.count("  FAIL  ")
    n_warn = out.count("  WARN  ")
    n_pass = out.count("  PASS  ")
    print(f"── summary: {n_pass} passed, {n_warn} warnings, {n_fail} failures")
    strict = "--strict" in sys.argv
    sys.exit(1 if n_fail or (strict and n_warn) else 0)
