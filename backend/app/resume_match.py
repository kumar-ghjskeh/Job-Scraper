"""Resume ↔ job matching, defensibility, safe tailoring, and interview prep.

All computed live from the stored resume profile so it always reflects the
current resume. Never suggests claiming a skill the resume/projects don't
support — suggestions are tiered Safe to Add / Reword Only / Learn First /
Do Not Add.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from .resume_parser import (
    HDLS, METHODOLOGIES, TOOLS, PROTOCOLS, CONCEPTS, LANGUAGES, PROJECT_SIGNALS,
)
from .scoring import (
    experienced_fit_score, new_grad_fit_score, overall_recommendation,
)

_ALL = {**HDLS, **METHODOLOGIES, **TOOLS, **PROTOCOLS, **CONCEPTS, **LANGUAGES}
_TOOLSET = set(TOOLS) | set(PROTOCOLS)  # things you must actually have used

# Skill equivalences → "Reword Only" (resume already proves it under another name)
_EQUIVALENT: dict[str, list[str]] = {
    "SVA": ["Functional Coverage", "Testbench"],
    "RTL Design": ["Verilog", "SystemVerilog", "Digital Design", "Logic Design"],
    "Digital Design": ["RTL Design", "Verilog", "SystemVerilog"],
    "Testbench": ["UVM", "SystemVerilog"],
    "AMBA": ["AXI", "AHB", "APB"],
    "Constrained Random": ["UVM"],
}

# Which broad area each skill belongs to (for Safe-to-Add vs Learn-First)
_AREA: dict[str, str] = {}
for _s in HDLS: _AREA[_s] = "rtl"
for _s in CONCEPTS:
    _AREA[_s] = "dft" if _s in ("DFT", "Scan", "ATPG", "MBIST", "Boundary Scan", "Fault Coverage") else "rtl"
for _s in METHODOLOGIES: _AREA[_s] = "dv"
for _s in PROTOCOLS: _AREA[_s] = "rtl"
for _s in TOOLS: _AREA[_s] = "tool"


@lru_cache(maxsize=8192)
def _extract_cached(t: str) -> tuple:
    return tuple(canon for canon, pats in _ALL.items() if any(re.search(p, t) for p in pats))


def extract_job_skills(job_text: str) -> list[str]:
    """Canonical skills/keywords found in the text. Cached (same posting text →
    same result) so the heavy taxonomy regex runs once per distinct posting."""
    return list(_extract_cached((job_text or "").lower()))


def job_skills_for(job: dict) -> list[str]:
    """Prefer the precomputed `job_skills` stored on the posting (fast split);
    fall back to live extraction when it isn't populated yet."""
    stored = job.get("job_skills")
    if stored:
        return [s for s in stored.split(",") if s]
    return extract_job_skills(" ".join([
        job.get("job_title", ""), job.get("cleaned_description", "") or "",
        job.get("matched_keywords", "") or "",
    ]))


def _area_strength(profile: dict) -> dict[str, int]:
    return {
        "dv": len(profile.get("methodologies", [])),
        "rtl": len(profile.get("hdls", [])) + len([c for c in profile.get("concepts", []) if _AREA.get(c) == "rtl"]),
        "dft": len([c for c in profile.get("concepts", []) if _AREA.get(c) == "dft"]),
        "tool": len(profile.get("tools", [])),
    }


def _classify_suggestion(skill: str, profile: dict, strengths: dict[str, int]) -> tuple[str, str]:
    """Return (tier, rationale) for a missing skill. Never fabricate."""
    resume_skills = set(profile.get("all_skills", []))
    # 1. Equivalent already present → reword
    for equiv in _EQUIVALENT.get(skill, []):
        if equiv in resume_skills:
            return "Reword Only", f"Your resume shows {equiv}; reword to surface “{skill}”."
    area = _AREA.get(skill, "tool")
    # 2. Specific tools/protocols you've never used → never claim
    if skill in _TOOLSET:
        if strengths.get("tool", 0) >= 3 or strengths.get(area, 0) >= 3:
            return "Learn First", f"Adjacent to your background, but learn {skill} before claiming it."
        return "Do Not Add", f"No supporting experience with {skill} — leave it off."
    # 3. Concept/methodology in a strong area → safe (implied by your work)
    if strengths.get(area, 0) >= 3:
        return "Safe to Add", f"Well-supported by your {area.upper()} experience — safe to make explicit."
    if strengths.get(area, 0) >= 1:
        return "Learn First", f"Some foundation, but strengthen {skill} before featuring it."
    return "Do Not Add", f"No supporting background for {skill} yet."


def _recommended_resume(role_category: str, profile: dict) -> str:
    rc = (role_category or "").lower()
    if "verification" in rc or rc in ("design verification",):
        return "DV / UVM Resume"
    if "formal" in rc:
        return "Formal Verification Resume"
    if "fpga" in rc:
        return "FPGA Resume"
    if "dft" in rc:
        return "DFT Resume"
    if "post-silicon" in rc or "validation" in rc:
        return "Post-Silicon Resume"
    if "eda" in rc:
        return "EDA / CAD Resume"
    if "rtl" in rc or "design" in rc:
        return "RTL Design Resume"
    focus = (profile.get("role_focus") or "").lower()
    if "verification" in focus:
        return "DV / UVM Resume"
    return "RTL Design Resume"


_INTERVIEW_TOPICS = {
    "Design Verification": ["UVM testbench architecture (driver/monitor/sequencer/scoreboard)",
        "SystemVerilog assertions (SVA)", "Functional coverage & coverage closure",
        "Constrained-random verification", "AXI/AMBA protocol checking", "CDC fundamentals",
        "Regression debug & triage"],
    "RTL Design": ["FSM design & encoding", "Pipelining & hazards", "Synthesizable RTL style",
        "Clock domain crossing", "Timing concepts (setup/hold)", "AXI/APB interfaces", "Low-power techniques"],
    "Formal Verification": ["Property/assertion writing (SVA)", "Formal proof vs bounded depth",
        "Equivalence checking", "Assume-guarantee", "Coverage in formal", "Convergence techniques"],
    "DFT": ["Scan insertion & scan chains", "ATPG & fault models", "MBIST architecture",
        "JTAG/boundary scan", "Compression", "Test coverage closure"],
    "FPGA": ["FPGA vs ASIC design tradeoffs", "Timing closure in Vivado/Quartus", "RTL for FPGA",
        "FPGA prototyping flow", "Clocking & resources"],
}


# Per-company interview emphasis for the top semiconductor employers (what their
# loops tend to stress). Generic fallback for everyone else.
_COMPANY_FOCUS = {
    "nvidia": "GPU/accelerator verification at scale — expect deep UVM, performance/coverage rigor, and demanding computer-architecture questions.",
    "amd": "CPU/GPU pipelines — strong computer-architecture and RTL/DV depth; cache coherence and high-speed protocols come up.",
    "intel": "Broad SoC/CPU — fundamentals-heavy loops, debug scenarios, and methodology depth.",
    "qualcomm": "Mobile SoC/modem — low-power, protocols (AXI/MIPI), and DV methodology; an online assessment is common.",
    "apple": "Custom silicon — a very high bar on fundamentals and project depth; keep answers concise and precise.",
    "broadcom": "Networking/connectivity ASICs — protocol-heavy (Ethernet/PCIe/SerDes) with DV rigor.",
    "marvell": "Infrastructure silicon — protocols, DV methodology, and architecture.",
    "micron": "Memory subsystems — DDR/LPDDR/HBM, controllers, and verification depth.",
    "tesla": "Custom autonomy/datacenter silicon — strong fundamentals and end-to-end ownership.",
    "arm": "IP/CPU — microarchitecture, AMBA/CHI, and crisp design reasoning.",
    "synopsys": "EDA/IP — verification methodology, formal/coverage depth, and tool fluency.",
    "cadence": "EDA/IP — verification methodology and protocol-IP depth.",
    "nxp": "Automotive/edge SoC — safety, protocols (CAN/Ethernet), and DV methodology.",
    "texas instruments": "Analog/mixed-signal & embedded — fundamentals, mixed-signal awareness, and rigor.",
    "cerebras": "Wafer-scale AI silicon — large-scale verification, performance, and systems thinking.",
    "tenstorrent": "RISC-V AI silicon — RISC-V architecture, RTL/DV depth, and open methodology.",
}


def _interview_rounds(tier: str, role_category: str) -> list[dict]:
    """Curated likely interview loop, adapted to company tier and role. Reflects
    the common shape of semiconductor RTL/DV loops (recruiter → OA/phone → onsite
    panels → behavioral); smaller companies run shorter loops."""
    rc = (role_category or "RTL Design").lower()
    is_dv = "verification" in rc or "formal" in rc or "validation" in rc
    core = ("SystemVerilog/UVM coding — build or extend a testbench component "
            "(driver/monitor/scoreboard), write an assertion or a coverage point." if is_dv else
            "RTL design problem — code a synthesizable block (FSM, FIFO, arbiter), then reason about timing and corner cases.")
    fundamentals = "Digital design & computer-architecture fundamentals — FSMs, pipelining, hazards, CDC, setup/hold, caches, number systems."
    deepdive = "Résumé & project deep-dive — walk your strongest project end-to-end: design decisions, bugs you found, coverage, and what you'd improve."
    debug = ("Debug / scenario round — given a failing simulation or waveform, methodically isolate the bug." if is_dv else
             "Debug / timing round — given a failing path or waveform, find the root cause and propose a fix.")
    behavioral = "Behavioral / hiring-manager — teamwork, ownership, why this team, handling conflict, and learning from a failure."
    recruiter = "15–30 min — background, logistics, work authorization/relocation, and role fit."

    if tier in ("S", "A"):
        return [
            {"name": "1 · Recruiter screen", "what": recruiter},
            {"name": "2 · Online assessment / technical phone", "what": "Timed HDL coding + fundamentals (SystemVerilog/Verilog, basic " + ("DV" if is_dv else "RTL") + ")."},
            {"name": "3 · Onsite — " + ("DV core" if is_dv else "RTL core"), "what": core},
            {"name": "4 · Onsite — fundamentals", "what": fundamentals},
            {"name": "5 · Onsite — project deep-dive", "what": deepdive},
            {"name": "6 · Onsite — debug", "what": debug},
            {"name": "7 · Behavioral / hiring manager", "what": behavioral},
        ]
    if tier == "B":
        return [
            {"name": "1 · Recruiter screen", "what": recruiter},
            {"name": "2 · Technical phone", "what": core},
            {"name": "3 · Onsite — fundamentals + project", "what": fundamentals + " Plus a project deep-dive."},
            {"name": "4 · Hiring manager / behavioral", "what": behavioral},
        ]
    return [
        {"name": "1 · Recruiter / founder screen", "what": recruiter},
        {"name": "2 · Technical", "what": core + " Expect fundamentals mixed in."},
        {"name": "3 · Team / behavioral", "what": behavioral},
    ]


def _interview_prep(role_category: str, job_skills: list[str], profile: dict,
                    tier: str = "", company: str = "") -> dict:
    base = _INTERVIEW_TOPICS.get(role_category, _INTERVIEW_TOPICS["RTL Design"])
    # JD-specific protocol topics on top of the role baseline.
    extra = [s for s in job_skills if s in PROTOCOLS][:3]
    topics = base + [f"{p} protocol details" for p in extra if f"{p} protocol details" not in base]
    # Résumé-defense questions from the candidate's own projects.
    defense = []
    for proj in profile.get("projects", [])[:4]:
        short = proj.split("—")[0].split("-")[0].strip()[:70]
        if short:
            defense.append(f"Walk through “{short}” — design choices, verification, and what you'd improve.")
    if profile.get("project_signals"):
        for sig in profile["project_signals"][:3]:
            defense.append(f"Be ready to defend your {sig} work in depth.")
    company_focus = _COMPANY_FOCUS.get((company or "").lower().strip(),
        f"Review {company}'s products and recent silicon, and connect your projects to what this team builds." if company else "")
    return {
        "rounds": _interview_rounds(tier, role_category),
        "company_focus": company_focus,
        "technical_topics": topics[:8],
        "resume_defense": defense[:6],
    }


_SENIOR_WORDS = ("senior", "sr.", "staff", "principal", "lead", "manager", "director", "fellow")


def _experience_fit(profile: dict, job: dict) -> int:
    """How realistic the role's seniority is for THIS candidate (0–100).

    Strict for a no-/low-experience resume: a *stated* years requirement the
    candidate doesn't meet, or a senior title, sharply lowers the fit — even if
    the posting is loosely tagged "entry level" (many "2+ yrs" roles are). A
    genuine new-grad role with no years bar scores 100."""
    yrs = profile.get("years_experience", 0) or 0
    level = (job.get("experience_level") or "").lower()
    title = (job.get("job_title") or "").lower()
    req_min = job.get("years_required_min")
    is_senior = job.get("is_senior") or any(w in level or w in title for w in _SENIOR_WORDS)
    entry_signal = job.get("is_entry_level") or any(
        k in level for k in ("new grad", "entry", "junior", "intern", "university", "graduate")
    )

    if yrs <= 1:  # new grad / no professional experience
        if is_senior:
            return 22  # senior / staff / principal — a real stretch
        # A concrete years requirement the candidate lacks dominates, even when
        # the posting is tagged entry-level — this is what a recruiter screens on.
        if req_min is not None and req_min >= 1:
            return {1: 78, 2: 55, 3: 40}.get(req_min, 26)
        if entry_signal:
            return 100  # genuine new-grad / entry role, no years bar
        if job.get("is_candidate_friendly") or "associate" in level or "mid" in level:
            return 70
        return 58  # level unknown, no stated requirement — plausible, unproven
    # experienced candidate
    if req_min is not None:
        if yrs >= req_min:
            return 95
        if yrs >= req_min - 2:
            return 75
        return 55
    if is_senior and yrs < 5:
        return 66
    return 78


def _domain_score(profile: dict, job: dict) -> int:
    """Role-category alignment with the resume's focus (0–100)."""
    rc = (job.get("role_category") or "").lower()
    focus = (profile.get("role_focus") or "").lower()
    if not rc or rc == "unknown":
        return 60
    if focus and (focus.split()[0] in rc or rc.split()[0] in focus):
        return 100
    dv = ("verification", "dv", "formal", "validation")
    if any(t in rc for t in dv) and any(t in focus for t in dv):
        return 90
    rtl = ("rtl", "design")
    if any(t in rc for t in rtl) and any(t in focus for t in rtl):
        return 85
    return 55


def compute_match(profile: dict, job: dict, lite: bool = False) -> dict:
    """job is a dict with job_title, cleaned_description, matched_keywords,
    role_category, match_score, is_candidate_friendly, eligibility_risk,
    sponsors_h1b, first_seen_at-ish freshness flag.

    lite=True returns only the scores + capped matched/missing skills — used for
    ranking the full job set fast (skips the per-job interview prep, tailoring
    suggestions, and why-matches that only the detail view needs)."""
    job_text = " ".join([
        job.get("job_title", ""), job.get("cleaned_description", "") or "",
        job.get("matched_keywords", "") or "",
    ])
    job_skills = job_skills_for(job)
    resume_skills = set(profile.get("all_skills", []))

    matched = [s for s in job_skills if s in resume_skills]
    missing = [s for s in job_skills if s not in resume_skills]

    # ── Resume-overlap sub-scores (each 0–100) ───────────────────────────────
    # 1. Skills: overlap ratio blended with absolute depth.
    if job_skills:
        overlap = len(matched) / len(job_skills)
        depth = min(1.0, len(matched) / 8)
        skills_score = round(100 * (0.5 * overlap + 0.5 * depth))
    else:
        skills_score = 45  # no parseable JD skills

    # 2. Matched projects (resume projects that touch the job's areas).
    job_signals = [s for s, pats in PROJECT_SIGNALS.items() if any(re.search(p, job_text.lower()) for p in pats)]
    matched_projects = []
    for proj in profile.get("projects", []):
        pl = proj.lower()
        if any(re.search(p, pl) for s in job_signals for p in PROJECT_SIGNALS[s]) or any(m.lower() in pl for m in matched[:6]):
            matched_projects.append(proj)
    matched_projects = matched_projects[:4]
    projects_score = [40, 70, 90, 100][min(len(matched_projects), 3)]

    # 3. Domain alignment (role category vs resume focus).
    domain_score = _domain_score(profile, job)

    # 4. Tool / protocol match — the specific tools/protocols the JD names.
    job_tools = [s for s in job_skills if s in _TOOLSET]
    matched_tools = [s for s in job_tools if s in resume_skills]
    tool_protocol_score = round(100 * len(matched_tools) / len(job_tools)) if job_tools else 60

    # ── Job-intrinsic fit scores (seniority reality, resume-independent) ──────
    lvl = job.get("experience_level", "") or ""
    is_sen = bool(job.get("is_senior"))
    ng_fit = job.get("new_grad_fit")
    if ng_fit is None:
        ng_fit = new_grad_fit_score(
            lvl, is_sen, bool(job.get("is_entry_level")),
            bool(job.get("is_candidate_friendly")), job.get("years_required_min"),
            job.get("job_title", ""), job.get("cleaned_description", ""),
        )
    exp_fit = job.get("experienced_fit")
    if exp_fit is None:
        exp_fit = experienced_fit_score(lvl, is_sen, job.get("years_required_min"))
    recommendation = overall_recommendation(ng_fit)

    # Raw résumé↔JD overlap (skills / projects / domain / tools) — no level term.
    overlap_match = round(
        0.50 * skills_score + 0.20 * projects_score
        + 0.20 * domain_score + 0.10 * tool_protocol_score
    )

    # ── Resume Match (what the user sees) = a PERSONALIZED, realistic match ──
    # Skills overlap dominates, but the role's seniority fit pulls it toward
    # reality so a Staff/Senior role can't read as a 97% match for a new-grad
    # résumé. Level fit adapts to the résumé: ranked by New Grad Fit for a
    # 0–2-yr candidate (senior roles drop), by Experienced Fit beyond that
    # (senior roles fit). This is what makes "Best Resume Match" accurate for
    # YOU rather than surfacing high-overlap roles you can't realistically get.
    yrs = profile.get("years_experience", 0) or 0
    level_fit = ng_fit if yrs < 3 else exp_fit
    resume_match = round(0.55 * overlap_match + 0.45 * level_fit)

    match_breakdown = {
        "skills": skills_score,
        "experience": ng_fit,          # "Experience / level fit" row = New Grad Fit
        "projects": projects_score,
        "domain": domain_score,
        "tool_protocol": tool_protocol_score,
    }

    # Defensibility (kept for compatibility; not shown in UI) — uses raw overlap.
    proj_factor = min(1.0, len(matched_projects) / 2)
    defensibility = round(100 * (0.55 * (overlap_match / 100) + 0.45 * proj_factor))

    # Apply priority — realistic roles for THIS candidate with a decent overlap.
    # Uses the RAW overlap (not the personalized resume_match) so level fit is not
    # double-counted. Eligibility risk only nudges.
    elig_pen = 12 if job.get("eligibility_risk") == "high" else (5 if job.get("eligibility_risk") == "medium" else 0)
    priority_score = 0.55 * level_fit + 0.45 * overlap_match - elig_pen
    apply_priority = "High" if priority_score >= 72 else ("Medium" if priority_score >= 52 else "Low")

    # Fast path for list ranking — everything the cards/sort need, none of the
    # heavy per-job detail (interview prep, suggestions, why-matches).
    if lite:
        return {
            "resume_match": resume_match,
            "new_grad_fit": ng_fit,
            "experienced_fit": exp_fit,
            "overall_recommendation": recommendation,
            "match_breakdown": match_breakdown,
            "defensibility": defensibility,
            "apply_priority": apply_priority,
            "apply_priority_score": round(priority_score, 1),
            "matched_skills": matched[:6],
            "missing_skills": missing[:6],
            "recommended_resume": _recommended_resume(job.get("role_category", ""), profile),
        }

    # Why matches
    why = []
    rc = job.get("role_category")
    if rc and rc != "Unknown":
        why.append(f"{rc} role aligned with your focus")
    if matched:
        why.append("Your skills: " + ", ".join(matched[:6]))
    if matched_projects:
        why.append(f"Backed by {len(matched_projects)} of your projects")
    if job.get("is_candidate_friendly"):
        why.append("Open to junior candidates")
    if job.get("sponsors_h1b") is True:
        why.append("Sponsors H1B")

    # Safe tailoring suggestions
    strengths = _area_strength(profile)
    suggestions = []
    for sk in missing[:10]:
        tier, rationale = _classify_suggestion(sk, profile, strengths)
        suggestions.append({"skill": sk, "tier": tier, "rationale": rationale})

    return {
        "resume_match": resume_match,
        "new_grad_fit": ng_fit,
        "experienced_fit": exp_fit,
        "overall_recommendation": recommendation,
        "match_breakdown": match_breakdown,
        "defensibility": defensibility,
        "apply_priority": apply_priority,
        "apply_priority_score": round(priority_score, 1),
        "matched_skills": matched,
        "missing_skills": missing,
        "matched_projects": matched_projects,
        "recommended_resume": _recommended_resume(job.get("role_category", ""), profile),
        "why_matches": why,
        "tailoring_suggestions": suggestions,
        "interview_prep": _interview_prep(
            rc if rc in _INTERVIEW_TOPICS else "RTL Design", job_skills, profile,
            tier=job.get("company_priority", "") or "", company=job.get("company", "") or "",
        ),
    }
