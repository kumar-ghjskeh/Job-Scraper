"""Guardrails proving the seniority classification is internally consistent and
that 'Best match' resume sorting respects the candidate's level.

These lock in the two real bugs found on production:
  1. A job could read "Entry Level" yet carry is_senior=True (two disagreeing
     engines) — so senior roles leaked through level-based filters.
  2. 'Best match' resume sort ranked Staff/Senior roles above entry roles for a
     no-experience resume because it sorted on pure skill overlap.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from backend.app.resume_match import compute_match
from backend.app.scoring import (
    _ENTRY_TIERS, _SENIOR_TIERS, classify_seniority, classify_seniority_flags,
)

# A representative spread of real titles seen in production.
_TITLES = [
    ("Design Verification Engineer", ""),
    ("Senior CPU Verification Engineer", ""),
    ("Staff Design Verification Engineer", ""),
    ("Sr Principal CPU Verification Engineer", ""),
    ("SoC Verification Lead", ""),
    ("Principal SoC Design Verification Engineer", ""),
    ("Engineering Manager, Silicon Verification", ""),
    ("Verification Architect", ""),
    ("RTL Design Engineer - MTS", ""),
    ("ASIC Verification Engineer", "0-3 years of experience preferred"),
    ("Design Verification Engineer, New College Grad 2026", ""),
    ("Junior Digital Design Engineer", ""),
    ("ASIC Engineer I", ""),
    ("CPU Verification Engineer", "Requires 10+ years of experience"),
]


def test_level_and_flags_never_contradict():
    """is_senior/is_entry are derived from the displayed level, so a job can never
    be both senior and entry, and the flags always match the level tier."""
    for title, desc in _TITLES:
        level, _ = classify_seniority(title, desc)
        is_entry, is_senior = classify_seniority_flags(title, desc)
        assert not (is_entry and is_senior), f"{title!r} is both entry and senior"
        assert is_senior == (level in _SENIOR_TIERS), f"{title!r}: senior flag != level {level}"
        assert is_entry == (level in _ENTRY_TIERS), f"{title!r}: entry flag != level {level}"


def test_architect_and_mts_titles_are_senior():
    for title in ("Verification Architect", "RTL Design Engineer - MTS",
                  "SMTS Design Verification Engineer"):
        _, is_senior = classify_seniority_flags(title, "")
        assert is_senior is True, f"{title!r} should be senior"


def test_description_senior_mention_does_not_flag_role_senior():
    """A JD that merely mentions 'senior engineers' must NOT mark the role senior
    (this keyword-bleed was falsely hiding ~50 legitimate non-senior roles)."""
    _, is_senior = classify_seniority_flags(
        "Design Verification Engineer",
        "You will collaborate with senior engineers building UVM testbenches.",
    )
    assert is_senior is False


def test_new_college_grad_title_is_not_senior():
    is_entry, is_senior = classify_seniority_flags(
        "AI Chip Design Engineer - New College Grad 2026", "")
    assert is_senior is False and is_entry is True


# ── Resume 'Best match' must respect level for a no-experience resume ──────────

_NEW_GRAD_PROFILE = {
    "years_experience": 0.0,
    "role_focus": "Design Verification",
    "all_skills": ["UVM", "SystemVerilog", "Verilog", "SVA", "Functional Coverage"],
    "methodologies": ["UVM", "SVA", "Functional Coverage"],
    "hdls": ["Verilog", "SystemVerilog"],
    "concepts": [],
    "tools": [],
    "projects": ["UVM testbench for an AXI DMA — built driver/monitor/scoreboard"],
    "project_signals": [],
}


def _job(title, level, is_senior, is_entry):
    return {
        "job_title": title,
        "cleaned_description": "UVM SystemVerilog functional coverage constrained random verification",
        "matched_keywords": "uvm systemverilog",
        "role_category": "Design Verification",
        "experience_level": level,
        "is_senior": is_senior,
        "is_entry_level": is_entry,
        "is_candidate_friendly": is_entry,
        "years_required_min": None,
        "match_score": 80,
    }


def test_best_match_ranks_entry_above_senior_for_new_grad():
    senior = compute_match(_NEW_GRAD_PROFILE,
                           _job("Staff Design Verification Engineer", "Staff", True, False))
    entry = compute_match(_NEW_GRAD_PROFILE,
                          _job("Design Verification Engineer, New College Grad", "New Grad", False, True))
    # The Staff role may have equal/higher pure skill overlap...
    assert senior["resume_match"] >= entry["resume_match"] - 10
    # ...but the level-aware Best-match score must rank the entry role higher.
    assert entry["apply_priority_score"] > senior["apply_priority_score"], (
        f"entry {entry['apply_priority_score']} !> senior {senior['apply_priority_score']}")
