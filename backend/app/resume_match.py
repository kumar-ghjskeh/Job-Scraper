"""Resume ↔ job matching, defensibility, safe tailoring, and interview prep.

All computed live from the stored resume profile so it always reflects the
current resume. Never suggests claiming a skill the resume/projects don't
support — suggestions are tiered Safe to Add / Reword Only / Learn First /
Do Not Add.
"""

from __future__ import annotations

import re
from typing import Optional

from .resume_parser import (
    HDLS, METHODOLOGIES, TOOLS, PROTOCOLS, CONCEPTS, LANGUAGES, PROJECT_SIGNALS,
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
    _AREA[_s] = "dft" if _s in ("DFT", "Scan", "ATPG", "MBIST") else "rtl"
for _s in METHODOLOGIES: _AREA[_s] = "dv"
for _s in PROTOCOLS: _AREA[_s] = "rtl"
for _s in TOOLS: _AREA[_s] = "tool"


def extract_job_skills(job_text: str) -> list[str]:
    t = (job_text or "").lower()
    return [canon for canon, pats in _ALL.items() if any(re.search(p, t) for p in pats)]


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


def _interview_prep(role_category: str, job_skills: list[str], profile: dict) -> dict:
    base = _INTERVIEW_TOPICS.get(role_category, _INTERVIEW_TOPICS["RTL Design"])
    # add JD-specific protocol topics
    extra = [s for s in job_skills if s in PROTOCOLS][:3]
    topics = base + [f"{p} protocol details" for p in extra if f"{p} protocol details" not in base]
    # resume-defense questions from the candidate's own projects
    defense = []
    for proj in profile.get("projects", [])[:4]:
        short = proj.split("—")[0].split("-")[0].strip()[:70]
        if short:
            defense.append(f"Walk through “{short}” — design choices, verification, and what you'd improve.")
    if profile.get("project_signals"):
        for sig in profile["project_signals"][:3]:
            defense.append(f"Be ready to defend your {sig} work in depth.")
    return {"technical_topics": topics[:8], "resume_defense": defense[:6]}


def compute_match(profile: dict, job: dict) -> dict:
    """job is a dict with job_title, cleaned_description, matched_keywords,
    role_category, match_score, is_candidate_friendly, eligibility_risk,
    sponsors_h1b, first_seen_at-ish freshness flag."""
    job_text = " ".join([
        job.get("job_title", ""), job.get("cleaned_description", "") or "",
        job.get("matched_keywords", "") or "",
    ])
    job_skills = extract_job_skills(job_text)
    resume_skills = set(profile.get("all_skills", []))

    matched = [s for s in job_skills if s in resume_skills]
    missing = [s for s in job_skills if s not in resume_skills]

    # Resume match % — blend overlap ratio with absolute depth so a job that
    # mentions only one skill can't outrank a rich, deeply-matched role.
    if job_skills:
        overlap = len(matched) / len(job_skills)
        depth = min(1.0, len(matched) / 8)
        match_pct = round(100 * (0.5 * overlap + 0.5 * depth))
    else:
        # no parseable JD skills (e.g. Workday list w/o description) → role-focus
        rc = (job.get("role_category") or "").lower()
        focus = (profile.get("role_focus") or "").lower()
        match_pct = 55 if (focus and focus.split()[0] in rc) else 40

    # Matched projects (resume projects that touch the job's areas)
    job_signals = [s for s, pats in PROJECT_SIGNALS.items() if any(re.search(p, job_text.lower()) for p in pats)]
    matched_projects = []
    for proj in profile.get("projects", []):
        pl = proj.lower()
        if any(re.search(p, pl) for s in job_signals for p in PROJECT_SIGNALS[s]) or any(m.lower() in pl for m in matched[:6]):
            matched_projects.append(proj)
    matched_projects = matched_projects[:4]

    # Defensibility
    proj_factor = min(1.0, len(matched_projects) / 2)
    defensibility = round(100 * (0.55 * (match_pct / 100) + 0.45 * proj_factor))

    # Apply priority
    rel = job.get("match_score", 0)
    fresh_bonus = 5 if job.get("is_fresh") else 0
    elig_pen = 20 if job.get("eligibility_risk") == "high" else (8 if job.get("eligibility_risk") == "medium" else 0)
    priority_score = 0.4 * rel + 0.5 * match_pct + fresh_bonus - elig_pen
    apply_priority = "High" if priority_score >= 72 else ("Medium" if priority_score >= 52 else "Low")

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
        "resume_match": match_pct,
        "defensibility": defensibility,
        "apply_priority": apply_priority,
        "matched_skills": matched,
        "missing_skills": missing,
        "matched_projects": matched_projects,
        "recommended_resume": _recommended_resume(job.get("role_category", ""), profile),
        "why_matches": why,
        "tailoring_suggestions": suggestions,
        "interview_prep": _interview_prep(rc if rc in _INTERVIEW_TOPICS else "RTL Design", job_skills, profile),
    }
