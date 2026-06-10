"""Tests for match scoring and job classification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from backend.app.scoring import (
    calculate_match_score,
    detect_experience_level,
    detect_role_category,
    detect_years_required,
    normalize_title,
)
from backend.app.models import ExperienceLevel, RoleCategory


def test_score_dv_new_grad_s_tier():
    score, kws, _ = calculate_match_score(
        job_title="Design Verification Engineer - New Grad",
        description="Seeking new grad with UVM and SystemVerilog skills. 0-2 years experience.",
        company_priority="S",
        location="Santa Clara, CA",
    )
    assert score >= 70, f"Expected >= 70, got {score}"
    assert "entry-level" in kws or "new grad" in kws or any("entry" in k for k in kws)


def test_score_senior_penalizes():
    score, _, _bd = calculate_match_score(
        job_title="Senior Staff Design Verification Engineer",
        description="10+ years of UVM experience required.",
        company_priority="S",
        location="San Jose, CA",
    )
    assert score < 50, f"Expected < 50, got {score}"


def test_score_pure_software_penalizes():
    score, _, _bd = calculate_match_score(
        job_title="Software Engineer - Backend",
        description="Python, Kubernetes, microservices.",
        company_priority="S",
        location="Remote",
    )
    assert score < 30, f"Expected < 30, got {score}"


def test_score_rtl_fpga():
    score, kws, _ = calculate_match_score(
        job_title="RTL Design Engineer",
        description="SystemVerilog RTL design for FPGA targets.",
        company_priority="A",
        location="Austin, TX",
    )
    assert score >= 50, f"Expected >= 50, got {score}"


def test_detect_experience_new_grad():
    exp = detect_experience_level("Design Verification Engineer - New Grad 2024", "")
    assert exp == ExperienceLevel.new_grad


def test_detect_experience_zero_three():
    exp = detect_experience_level("ASIC Verification Engineer", "0-3 years of experience preferred")
    assert exp == ExperienceLevel.zero_to_three


def test_detect_role_dv():
    cat = detect_role_category("Design Verification Engineer", "UVM testbench")
    assert cat == "Design Verification"


def test_detect_role_fpga():
    cat = detect_role_category("FPGA Design Engineer", "RTL coding for FPGA")
    assert cat == "FPGA RTL"


def test_years_range():
    ymin, ymax = detect_years_required("0-3 years of relevant experience preferred.")
    assert ymin == 0 and ymax == 3


def test_years_plus():
    ymin, ymax = detect_years_required("Requires 5+ years experience")
    assert ymin == 5 and ymax is None


def test_normalize_title():
    t = normalize_title("Design Verification Engineer (New Grad) - Remote")
    assert "new grad" not in t
    assert "remote" not in t
    assert "design verification engineer" in t
