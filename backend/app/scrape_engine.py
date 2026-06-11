"""Scrape orchestration engine — runs all companies and persists results."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from .apply_url import process_apply_url
from .config import load_companies, load_schedule
from .database import engine
from .description_cleaner import clean_html_description, truncate_description_cleanly
from .eligibility import detect_eligibility_risk
from .location_utils import parse_location
from .models import ActiveStatus, Company, JobPosting, ScrapeError, ScrapeRun
from .scrapers import get_scraper
from .quality import (
    canonical_location_label,
    compute_data_quality,
    source_reliability,
)
from .scoring import (
    build_relevance_reason,
    calculate_match_score,
    classify_role_flags,
    classify_seniority,
    classify_seniority_flags,
    detect_experience_level,
    detect_remote_status,
    detect_role_category,
    detect_years_required,
    is_candidate_friendly_job,
    is_software_only,
    normalize_title,
    score_breakdown_json,
    score_to_label,
)
from .services.alerts import send_alerts
from .services.dedupe import find_existing
from .services.notion_sync import sync_job_to_notion

logger = logging.getLogger(__name__)

# After this many consecutive failed runs a source is auto-quarantined (skipped)
# so broken endpoints never keep throwing errors into the dashboard.
ERROR_QUARANTINE_THRESHOLD = 8


async def run_scrape(triggered_by: str = "scheduler", priorities: set[str] | None = None) -> ScrapeRun:
    schedule_cfg = load_schedule()
    delay_between = schedule_cfg.get("rate_limit", {}).get("delay_between_companies_seconds", 5)
    removed_threshold = schedule_cfg.get("removed_job_threshold", 2)

    run = ScrapeRun(triggered_by=triggered_by)
    with Session(engine) as session:
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    companies = load_companies()
    if priorities:
        # Tier-based sync: only scrape companies in the requested priority tiers.
        companies = [c for c in companies if c.get("priority", "C") in priorities]
    total_new = 0
    total_found = 0
    total_errors = 0
    total_removed = 0
    scraped_count = 0
    found_per_company: dict[str, set[str]] = {}

    for company_cfg in companies:
        company_name = company_cfg["name"]
        found_per_company[company_name] = set()

        # Skip auto-quarantined sources (too many prior consecutive failures)
        with Session(engine) as session:
            co = session.exec(select(Company).where(Company.name == company_name)).first()
            if co and co.scrape_error_count >= ERROR_QUARANTINE_THRESHOLD:
                logger.warning(
                    "Skipping %s — quarantined after %d failures",
                    company_name, co.scrape_error_count,
                )
                continue

        scraper = get_scraper(company_cfg)

        try:
            async with scraper:
                raw_jobs = await scraper.fetch_jobs()

            scraped_count += 1
            total_found += len(raw_jobs)
            now = datetime.now(timezone.utc)

            with Session(engine) as session:
                for raw in raw_jobs:
                    job_id_str = raw.job_id or ""
                    found_per_company[company_name].add(job_id_str or raw.apply_url)

                    existing = find_existing(
                        session,
                        company=company_name,
                        job_title=raw.job_title,
                        location=raw.location,
                        job_id=job_id_str,
                        apply_url=raw.apply_url,
                    )

                    if existing:
                        existing.last_seen_at = now
                        existing.active_status = ActiveStatus.active
                        existing.missed_scrapes = 0
                        if raw.description_snippet and not existing.description_snippet:
                            existing.description_snippet = raw.description_snippet
                            existing.cleaned_description = clean_html_description(raw.description_snippet)
                        session.add(existing)
                    else:
                        total_new += 1

                        # Clean HTML from description before any processing
                        raw_desc = raw.full_description_text or raw.description_snippet or ""
                        cleaned_desc = clean_html_description(raw_desc)
                        snippet = truncate_description_cleanly(
                            raw.description_snippet or raw_desc, length=300
                        )

                        # Location parsing
                        loc_result = parse_location(raw.location, snippet)

                        # Apply URL safety
                        url_result = process_apply_url(
                            raw.apply_url,
                            company_cfg.get("ats_platform", ""),
                            company_name,
                        )

                        # Scoring (uses cleaned text for accuracy)
                        score, matched_kws, breakdown = calculate_match_score(
                            job_title=raw.job_title,
                            description=cleaned_desc,
                            company_priority=company_cfg.get("priority", "C"),
                            location=raw.location,
                            is_usa=loc_result.is_usa,
                            first_seen_recently=True,
                            ats_platform=company_cfg.get("ats_platform", ""),
                        )

                        exp = detect_experience_level(raw.job_title, cleaned_desc)
                        role_cat = detect_role_category(raw.job_title, cleaned_desc)
                        remote_status = detect_remote_status(raw.location, cleaned_desc)
                        ymin, ymax = detect_years_required(cleaned_desc)
                        is_entry, is_senior = classify_seniority_flags(raw.job_title, cleaned_desc)
                        is_cand_friendly = is_candidate_friendly_job(
                            raw.job_title, cleaned_desc,
                            company_cfg.get("priority", "C"),
                            company_cfg.get("ats_platform", ""),
                        )
                        role_flags = classify_role_flags(raw.job_title, cleaned_desc)
                        sw_only = is_software_only(raw.job_title, cleaned_desc)
                        hw_sw = role_flags.get("is_hardware_software_codesign", False)
                        relevance = build_relevance_reason(raw.job_title, cleaned_desc, breakdown)
                        elig_risk, elig_terms = detect_eligibility_risk(cleaned_desc)

                        # Phase 2: granular seniority, location label, data quality
                        sen_level, sen_conf = classify_seniority(raw.job_title, cleaned_desc)
                        role_known = bool(role_cat) and role_cat != "Unknown"
                        src_rel = source_reliability(company_cfg.get("ats_platform", ""))
                        posted_known = raw.posted_date is not None
                        loc_label = canonical_location_label(
                            raw.location, loc_result.is_usa, loc_result.is_remote_usa,
                            remote_status, loc_result.confidence,
                        )
                        dq_score, class_conf = compute_data_quality(
                            has_description=bool(cleaned_desc),
                            location_confidence=loc_result.confidence,
                            posted_known=posted_known,
                            apply_status=url_result.apply_url_status,
                            role_known=role_known,
                            seniority_confidence=sen_conf,
                        )

                        import json
                        job = JobPosting(
                            company=company_name,
                            company_category=company_cfg.get("category", ""),
                            company_priority=company_cfg.get("priority", "C"),
                            job_title=raw.job_title,
                            normalized_title=normalize_title(raw.job_title),
                            role_category=role_cat,
                            experience_level=sen_level,
                            is_entry_level=is_entry,
                            is_candidate_friendly=is_cand_friendly,
                            is_senior=is_senior,
                            years_required_min=ymin,
                            years_required_max=ymax,
                            location=raw.location,
                            location_raw=raw.location,
                            remote_status=remote_status,
                            is_usa=loc_result.is_usa,
                            is_remote_usa=loc_result.is_remote_usa,
                            country=loc_result.country,
                            state=loc_result.state,
                            city=loc_result.city,
                            location_confidence=loc_result.confidence,
                            job_id_from_company=job_id_str,
                            apply_url=url_result.safe_apply_url or raw.apply_url,
                            original_apply_url=url_result.original_apply_url,
                            safe_apply_url=url_result.safe_apply_url,
                            apply_url_status=url_result.apply_url_status,
                            apply_url_reason=url_result.apply_url_reason,
                            source_url=raw.source_url,
                            ats_platform=company_cfg.get("ats_platform", ""),
                            posted_date=raw.posted_date,
                            first_seen_at=now,
                            last_seen_at=now,
                            active_status=ActiveStatus.active,
                            match_score=score,
                            matched_keywords=", ".join(matched_kws),
                            score_breakdown_json=score_breakdown_json(breakdown),
                            relevance_score_label=score_to_label(score),
                            description_snippet=snippet,
                            full_description_text=raw.full_description_text or "",
                            cleaned_description=cleaned_desc,
                            role_flags_json=json.dumps(role_flags),
                            is_software_only=sw_only,
                            is_hardware_software_codesign=hw_sw,
                            relevance_reason=relevance,
                            matched_positive_terms_json=json.dumps(matched_kws),
                            data_quality_status="ok" if cleaned_desc else "no_description",
                            eligibility_risk=elig_risk,
                            eligibility_terms=", ".join(elig_terms),
                            seniority_confidence=sen_conf,
                            classification_confidence=class_conf,
                            data_quality_score=dq_score,
                            source_reliability=src_rel,
                            location_label=loc_label,
                            posted_date_known=posted_known,
                        )
                        session.add(job)
                        session.commit()
                        session.refresh(job)

                        await send_alerts(job)
                        await sync_job_to_notion(job)

                session.commit()

            removed = await _update_removed_status(
                company_name, found_per_company[company_name], removed_threshold
            )
            total_removed += removed

            with Session(engine) as session:
                co = session.exec(select(Company).where(Company.name == company_name)).first()
                if co:
                    co.last_scraped_at = now
                    co.scrape_error_count = 0  # reset on success — self-healing
                    session.add(co)
                    session.commit()

        except Exception as e:
            total_errors += 1
            logger.error("Scrape failed for %s: %s", company_name, e, exc_info=True)
            with Session(engine) as session:
                err = ScrapeError(
                    scrape_run_id=run_id,
                    company=company_name,
                    error_message=str(e),
                    error_type=type(e).__name__,
                )
                session.add(err)

                co = session.exec(select(Company).where(Company.name == company_name)).first()
                if co:
                    co.scrape_error_count += 1
                    session.add(co)
                session.commit()

        await asyncio.sleep(delay_between)

    with Session(engine) as session:
        run_obj = session.get(ScrapeRun, run_id)
        if run_obj:
            run_obj.finished_at = datetime.now(timezone.utc)
            run_obj.companies_scraped = scraped_count
            run_obj.jobs_found = total_found
            run_obj.new_jobs = total_new
            run_obj.removed_jobs = total_removed
            run_obj.errors = total_errors
            session.add(run_obj)
            session.commit()
            return run_obj

    return run


async def _update_removed_status(company: str, seen_ids: set[str], threshold: int) -> int:
    removed_count = 0
    with Session(engine) as session:
        active_jobs = session.exec(
            select(JobPosting).where(
                JobPosting.company == company,
                JobPosting.active_status.in_([ActiveStatus.active, ActiveStatus.possibly_removed]),
            )
        ).all()

        for job in active_jobs:
            uid = job.job_id_from_company or job.apply_url
            if uid not in seen_ids:
                job.missed_scrapes += 1
                if job.missed_scrapes >= threshold:
                    job.active_status = ActiveStatus.removed
                    job.removed_at = datetime.now(timezone.utc)
                    removed_count += 1
                else:
                    job.active_status = ActiveStatus.possibly_removed
                session.add(job)

        session.commit()
    return removed_count
