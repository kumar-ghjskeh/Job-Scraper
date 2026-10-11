"""Neither deploy target may be broken by something that is not a code defect.

Two outages ran at the same time and sent the same kind of mail:

1. The SCRAPE looked like it was failing. It wasn't — the scrape step succeeded
   on every run. `scripts/audit_system.py` ran `npm run build` as its last
   check, the scrape runners install Python only and have no node_modules, so
   npm exited non-zero, the audit reported a failure, and the publish step was
   skipped. Two days of green scrapes behind a gate that could not pass.

2. RENDER showed "Deploy failed". The startup handler was guarded against
   raising, but not against hanging, and uvicorn accepts no connection until it
   returns. libpq has no default connect timeout, so an unreachable database
   host (a suspended free instance, a name that no longer resolves, a dropped
   SYN) held the port shut for the whole TCP retry window — ~21s on Windows,
   ~127s on Linux. Render's deploy health check got nothing and failed the
   deploy for code that had not changed since the previous success.

Both have the same shape: infrastructure that cannot answer turns into a
reported failure of the application. These tests pin the three fixes.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


# ───────────────────────────────── the scrape gate ──────────────────────────

def test_scrape_workflows_do_not_gate_on_the_frontend_build():
    """The runners install Python only, so the audit must be told --no-build.

    Without it the audit fails on every scheduled run and the publish step is
    skipped — a green scrape that never reaches the CDN.
    """
    for name in ("scrape.yml", "scrape-giants.yml"):
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        audits = [ln.strip() for ln in text.splitlines() if "audit_system.py" in ln]
        assert audits, f"{name} no longer audits the corpus before publishing"
        for line in audits:
            assert "--no-build" in line, (
                f"{name} runs the audit without --no-build: {line!r}. This runner "
                f"has no node_modules, so the build check cannot pass and the "
                f"publish step will be skipped."
            )


def test_audit_treats_a_missing_toolchain_as_a_warning():
    """A check that CANNOT RUN is a warning. Only a real compile error fails."""
    src = (ROOT / "scripts" / "audit_system.py").read_text(encoding="utf-8")
    fn = src[src.index("def check_frontend_builds"):]
    fn = fn[:fn.index("\ndef ", 1)] if "\ndef " in fn[1:] else fn
    assert "node_modules" in fn, (
        "check_frontend_builds() must verify its precondition before running "
        "npm, or it fails wherever the frontend is not installed"
    )
    guard = fn[fn.index("node_modules"):]
    assert re.search(r"warn\(", guard.split("try:")[0]), (
        "a missing node_modules must downgrade to warn(), not fail()"
    )


# ──────────────────────────────── the Render deploy ─────────────────────────

def test_postgres_connections_are_bounded():
    """libpq's default is no timeout at all, so the ceiling must be explicit."""
    from backend.app import database

    # The local default is SQLite, so assert on how the kwargs are built rather
    # than on a live Postgres engine.
    src = (ROOT / "backend" / "app" / "database.py").read_text(encoding="utf-8")
    assert "connect_timeout" in src, (
        "Postgres connect_args needs connect_timeout: without it an unreachable "
        "host blocks for the OS TCP retry window (~127s on Linux), which fails "
        "Render's deploy health check"
    )
    assert "pool_timeout" in src, (
        "a saturated pool must not queue callers indefinitely"
    )
    assert database._connect_args.get("check_same_thread") is False, (
        "the SQLite branch must keep check_same_thread=False"
    )


def test_startup_does_not_block_on_a_hanging_database(monkeypatch):
    """The port must open on a short budget even if the DB never answers.

    This is the regression that mattered: a try/except around the seeding caught
    exceptions but not latency, and latency is what failed the deploy.
    """
    # `backend.app.main`, not `app.main`: both name the same file, but importing
    # it twice under two names registers the SQLModel tables twice in one
    # SQLAlchemy registry and the second import raises. The rest of the suite
    # uses this spelling; the Render spelling is checked in a subprocess below.
    from backend.app import main

    started = threading.Event()
    release = threading.Event()

    def never_returns():
        started.set()
        release.wait(30)  # stands in for a blackholed TCP connect

    monkeypatch.setattr(main, "_seed_and_maintain", never_returns)
    monkeypatch.setattr(main, "_SEED_BUDGET_SECONDS", 0.5)

    import asyncio

    t0 = time.monotonic()
    try:
        asyncio.run(main.startup())
        elapsed = time.monotonic() - t0
    finally:
        release.set()

    assert started.is_set(), "the seeding never ran at all"
    assert elapsed < 5, (
        f"startup took {elapsed:.1f}s against a database that never answers. "
        f"uvicorn accepts no connection until startup returns, so this is "
        f"exactly how long Render's health check waits on a closed port."
    )


def test_render_only_redeploys_when_the_backend_changes():
    """A deploy that never starts cannot fail.

    The scrape commits a snapshot 6x a day. Those commits touch no backend file,
    and every one of them used to run a full pip install and restart the free
    instance — 44 of 55 deploys in one week, each a chance to mail "Deploy
    failed" about unchanged code.
    """
    cfg = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    svc = cfg["services"][0]
    bf = svc.get("buildFilter")
    assert bf, "render.yaml has no buildFilter, so every data commit redeploys the API"
    assert "backend/**" in bf["paths"], "backend changes must still deploy"
    ignored = bf.get("ignoredPaths", [])
    assert any(p.startswith("frontend") for p in ignored), (
        "frontend/** carries the published snapshot and must not trigger a deploy"
    )


def test_the_api_imports_the_way_render_runs_it():
    """rootDir is backend, so the package is `app`, never `backend.app`.

    An import that only resolves from the repo root passes every local check and
    fails the deploy.
    """
    cfg = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    svc = cfg["services"][0]
    assert svc["rootDir"] == "backend"
    assert "app.main:app" in svc["startCommand"]

    # In a subprocess, with cwd=backend, so the import resolves the way the
    # start command does and nothing lands in this process's table registry.
    # This is the check that would have caught the Render outage where main.py
    # reached the scrape engine through snapshot.py.
    proc = subprocess.run(
        [sys.executable, "-c", "import app.main; print('ok')"],
        cwd=ROOT / "backend", capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0 and "ok" in proc.stdout, (
        "`uvicorn app.main:app` cannot import from rootDir=backend, so the "
        f"Render deploy will fail:\n{proc.stderr[-2000:]}"
    )


def test_health_answers_without_touching_the_database():
    """Render polls /health to decide whether a deploy succeeded.

    If it reads the database, a cold or missing database turns into a failed
    deploy for code that is fine.
    """
    import inspect

    from backend.app import main

    health = next(r for r in main.app.routes if getattr(r, "path", "") == "/health")
    body = inspect.getsource(health.endpoint)
    for forbidden in ("Session", "select(", "engine"):
        assert forbidden not in body, (
            f"/health touches the database ({forbidden!r}) — it must answer from "
            f"memory, or an unreachable DB reads as a failed deploy."
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
