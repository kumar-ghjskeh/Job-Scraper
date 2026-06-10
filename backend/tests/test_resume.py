"""Phase 3: resume parsing and match engine (incl. safe-tailoring tiers)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from backend.app.resume_parser import parse_resume
from backend.app.resume_match import compute_match

SAMPLE = (
    b"Sai Kumar\n"
    b"MS Electrical and Computer Engineering, Expected May 2026\n"
    b"Skills: SystemVerilog, UVM, SVA, Verilog, Python, AXI, functional coverage, "
    b"constrained random, VCS, Verdi\n"
    b"Projects:\n"
    b"- AXI4 UVM Verification Environment with scoreboard and functional coverage\n"
    b"- Async FIFO CDC project\n"
    b"- RISC-V pipeline CPU in Verilog\n"
    b"Experience: Design Verification Intern\n"
)


def _profile():
    return parse_resume(SAMPLE, "resume.txt").to_dict()


def test_parse_skills_and_focus():
    p = parse_resume(SAMPLE, "resume.txt")
    assert "UVM" in p.all_skills and "SystemVerilog" in p.all_skills and "AXI" in p.all_skills
    assert p.degree == "MS"
    assert p.role_focus == "Design Verification"
    assert len(p.projects) >= 2


def test_match_dv_job_has_matched_skills():
    job = {
        "job_title": "Design Verification Engineer",
        "cleaned_description": "Build UVM testbenches with SystemVerilog, SVA, functional coverage, AXI protocol verification, constrained random.",
        "matched_keywords": "uvm, systemverilog", "role_category": "Design Verification",
        "match_score": 80, "is_candidate_friendly": True, "eligibility_risk": "low",
        "sponsors_h1b": True, "is_fresh": True,
    }
    m = compute_match(_profile(), job)
    assert "UVM" in m["matched_skills"] and "SVA" in m["matched_skills"]
    assert m["resume_match"] > 0
    assert m["recommended_resume"] == "DV / UVM Resume"
    assert m["interview_prep"]["technical_topics"]


def test_tailoring_never_fabricates_tools():
    """A tool the resume has never used must be Do Not Add or Learn First — never Safe to Add."""
    job = {
        "job_title": "Formal Verification Engineer",
        "cleaned_description": "JasperGold formal verification, property checking.",
        "matched_keywords": "", "role_category": "Formal Verification",
        "match_score": 70, "is_candidate_friendly": False, "eligibility_risk": "low",
        "sponsors_h1b": True, "is_fresh": False,
    }
    m = compute_match(_profile(), job)
    jasper = [s for s in m["tailoring_suggestions"] if s["skill"] == "JasperGold"]
    assert jasper, "JasperGold should appear as a missing skill"
    assert jasper[0]["tier"] in ("Do Not Add", "Learn First")


def test_reword_for_equivalent_skill():
    """RTL Design missing but Verilog present → Reword Only, not Learn/Do-Not."""
    job = {
        "job_title": "RTL Design Engineer",
        "cleaned_description": "RTL design in Verilog, synthesis, microarchitecture.",
        "matched_keywords": "", "role_category": "RTL Design",
        "match_score": 75, "is_candidate_friendly": True, "eligibility_risk": "low",
        "sponsors_h1b": True, "is_fresh": True,
    }
    m = compute_match(_profile(), job)
    rtl = [s for s in m["tailoring_suggestions"] if s["skill"] == "RTL Design"]
    if rtl:
        assert rtl[0]["tier"] == "Reword Only"


def test_matched_projects_detected():
    job = {
        "job_title": "Verification Engineer",
        "cleaned_description": "AXI protocol verification with UVM and FIFO design.",
        "matched_keywords": "", "role_category": "Design Verification",
        "match_score": 70, "is_candidate_friendly": True, "eligibility_risk": "low",
        "sponsors_h1b": True, "is_fresh": True,
    }
    m = compute_match(_profile(), job)
    assert len(m["matched_projects"]) >= 1
