"""Application configuration — loads from .env and YAML config files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # rtl-dv-job-radar/
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # Database
    database_url: str = f"sqlite:///{DATA_DIR / 'jobs.db'}"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Optional Notion
    notion_api_key: str = ""
    notion_database_id: str = ""

    # Optional alerts
    alert_email_from: str = ""
    alert_email_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Scraper
    scraper_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    request_timeout_seconds: int = 30
    playwright_headless: bool = True

    # Run one scrape shortly after startup (used on fresh cloud deploys so the
    # dashboard is populated without waiting for the first scheduled run).
    run_scrape_on_startup: bool = False

    # Run the in-process APScheduler (tier-based scrapes + daily digest). OFF by
    # default: scraping is done externally by GitHub Actions (scrape.yml), so the
    # web service stays a lean read-only API. Enabling it on the free Render tier
    # makes scrapes compete with request serving and trips the health check.
    enable_scheduler: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_companies() -> list[dict]:
    """Enabled companies only — used by the scraper."""
    data = _load_yaml(CONFIG_DIR / "companies.yaml")
    return [c for c in data.get("companies", []) if c.get("enabled", True)]


def load_all_companies() -> list[dict]:
    """Every company (enabled + disabled 'Direct search') — used to seed the
    directory so the Companies page lists all of them, with the unscrapable ones
    linking out to their careers site."""
    data = _load_yaml(CONFIG_DIR / "companies.yaml")
    return list(data.get("companies", []))


def load_browser_companies() -> list[dict]:
    """Companies marked ``engine: browser`` — scraped only by the local
    real-browser runner (run_browser_scrape), never by the httpx scheduler.
    Selected by the engine flag regardless of ``enabled`` so they can stay
    excluded from the cloud scheduler while still being scraped locally."""
    data = _load_yaml(CONFIG_DIR / "companies.yaml")
    return [c for c in data.get("companies", []) if c.get("engine") == "browser"]


def company_engines() -> dict[str, str]:
    """Map lowercased company name -> engine flag ('' = httpx cloud, 'cf' =
    curl_cffi runner, 'browser' = Playwright). Used to tell the directory which
    'enabled:false' companies are actually auto-connected via a local/CI runner
    (so they aren't mislabeled 'Direct search')."""
    data = _load_yaml(CONFIG_DIR / "companies.yaml")
    return {c["name"].lower(): (c.get("engine") or "") for c in data.get("companies", [])}


def load_cf_companies() -> list[dict]:
    """Companies marked ``engine: cf`` — Cloudflare-walled sites scraped via
    curl_cffi (Chrome TLS impersonation) by the local cf runner (run_cf_scrape),
    never by the cloud httpx scheduler. Selected by the engine flag regardless of
    ``enabled``."""
    data = _load_yaml(CONFIG_DIR / "companies.yaml")
    return [c for c in data.get("companies", []) if c.get("engine") == "cf"]


def load_keywords() -> dict:
    return _load_yaml(CONFIG_DIR / "keywords.yaml")


def load_schedule() -> dict:
    return _load_yaml(CONFIG_DIR / "schedule.yaml")


settings = Settings()

DATA_DIR.mkdir(parents=True, exist_ok=True)
