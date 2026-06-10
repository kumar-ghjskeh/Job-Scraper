"""Tests for entry-level, senior, and candidate-friendly classification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from backend.app.scoring import (
    classify_seniority_flags,
    is_candidate_friendly_job,
    detect_experience_level,
)
from backend.app.models import ExperienceLevel


# ── Entry-level / Senior flags ────────────────────────────────────────────────

def test_new_grad_is_entry_level():
    is_entry, is_senior = classify_seniority_flags("Design Verification Engineer New Grad", "")
    assert is_entry is True
    assert is_senior is False


def test_senior_title_is_senior():
    is_entry, is_senior = classify_seniority_flags("Senior RTL Design Engineer", "")
    assert is_senior is True
    assert is_entry is False


def test_staff_title_is_senior():
    is_entry, is_senior = classify_seniority_flags("Staff Verification Engineer", "")
    assert is_senior is True


def test_principal_title_is_senior():
    is_entry, is_senior = classify_seniority_flags("Principal Design Engineer", "")
    assert is_senior is True


def test_plain_dv_engineer_not_senior():
    is_entry, is_senior = classify_seniority_flags("Design Verification Engineer", "")
    assert is_senior is False


def test_zero_three_years_entry():
    is_entry, is_senior = classify_seniority_flags(
        "ASIC Verification Engineer", "0-3 years of experience preferred"
    )
    assert is_entry is True


def test_ten_plus_years_senior():
    is_entry, is_senior = classify_seniority_flags(
        "Hardware Verification Engineer", "10+ years of experience required"
    )
    assert is_senior is True
    assert is_entry is False


# ── Candidate-friendly ────────────────────────────────────────────────────────

def test_candidate_friendly_dv_s_tier():
    assert is_candidate_friendly_job(
        "Design Verification Engineer", "UVM, SystemVerilog", "S", "greenhouse"
    ) is True


def test_not_candidate_friendly_senior():
    assert is_candidate_friendly_job(
        "Senior Design Verification Engineer", "UVM", "S", "greenhouse"
    ) is False


def test_not_candidate_friendly_c_tier():
    assert is_candidate_friendly_job(
        "RTL Design Engineer", "Verilog FPGA", "C", "lever"
    ) is False


def test_candidate_friendly_rtl_a_tier():
    assert is_candidate_friendly_job(
        "RTL Design Engineer", "SystemVerilog ASIC", "A", "ashby"
    ) is True


def test_not_candidate_friendly_non_hw():
    assert is_candidate_friendly_job(
        "Software Engineer", "Python Kubernetes", "S", "greenhouse"
    ) is False


# ── ExperienceLevel enum ──────────────────────────────────────────────────────

def test_detect_level_entry_explicit():
    assert detect_experience_level("Verification Engineer Entry Level", "") == ExperienceLevel.entry_level


def test_detect_level_senior_explicit():
    assert detect_experience_level("Senior Verification Engineer", "") == ExperienceLevel.senior
