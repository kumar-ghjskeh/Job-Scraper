"""The board is for RTL design and RTL verification. Backend work is not that.

Physical design — floorplan, place-and-route, STA, timing closure, signoff — is a
separate career track from RTL design and verification, and it was leaking into
every visible category. 87 of 790 visible US jobs (11%) were backend roles, filed
as "RTL Design" (30 of them) and even "Formal Verification" (12), because:

  1. detect_role_category matched against title + description, and chip-company
     descriptions mention UVM, testbenches and coverage whatever the role is, so a
     "Physical Design Engineer" was classified by its own boilerplate; and
  2. the title-level fallback mapped "physical design" straight to RTL Design.

Physical Design is now its own category, decided on the TITLE ALONE and before
every other check, and hidden from the default view rather than deleted.
"""

from __future__ import annotations

from backend.app.models import RoleCategory
from backend.app.scoring import _PHYSICAL_DESIGN_TITLE, detect_role_category

# Real titles taken from the live corpus.
BACKEND_TITLES = [
    "Physical Design Engineer",
    "Principal Physical Design Engineer, STA",
    "Physical Design Engineer - Flow & Methodologies",
    "Physical Design Engineer - Full Chip Implementation",
    "Senior ASIC Floorplan Design Engineer",
    "SoC Timing (Static Timing Analysis/STA) Engineer, HBM",
    "ASIC/SOC Silicon Physical Design Engineer",
    "Senior ASIC Timing Engineer",
    "Sr. Staff Physical Design Timing Engineer (STA)",
    "Advanced ASIC Physical Design Lead",
    "Place and Route Engineer",
    "HBM SoC Physical Design Engineer",
]

IN_SCOPE_TITLES = [
    "Senior ASIC Design Verification Engineer",
    "RTL Design Engineer",
    "Staff Design Verification Engineer",
    "Senior Staff RTL Design Engineer",
    "Digital Design Engineer",
    "SoC Verification Engineer",
    "FPGA Verification Engineer",
    "Formal Verification Engineer",
    "Emulation Engineer",
    "Principal Engineer, Microarchitecture",
]


def test_backend_titles_are_classified_as_physical_design():
    wrong = [t for t in BACKEND_TITLES
             if detect_role_category(t) != RoleCategory.physical_design]
    assert not wrong, (
        "These backend-implementation titles are not classified as Physical "
        "Design, so they show in the RTL/DV view:\n  " + "\n  ".join(wrong)
    )


def test_rtl_and_verification_titles_are_not_swept_up():
    """The pattern must not be greedy. An early version lost its word boundaries
    and `sta` then matched "Staff", which would have reclassified a large share of
    the real RTL and DV postings as backend work."""
    swept = [t for t in IN_SCOPE_TITLES
             if detect_role_category(t) == RoleCategory.physical_design]
    assert not swept, (
        "These in-scope titles were classified as Physical Design:\n  "
        + "\n  ".join(swept)
    )


def test_word_boundaries_are_present_on_the_short_abbreviations():
    """sta, cts, drc, lvs, gds are short enough to appear inside ordinary words."""
    for title in ("Staff Engineer", "Installation Technician", "Statistician",
                  "Broadcast Engineer", "Logistics Analyst"):
        assert not _PHYSICAL_DESIGN_TITLE.search(title), (
            f"{title!r} matched the physical-design pattern — a boundary is "
            "missing on one of the short abbreviations."
        )


def test_description_mentioning_physical_design_does_not_reclassify_an_rtl_role():
    """Title-only is the point: RTL teams routinely describe working WITH the
    physical design team, and that must not move the posting out of scope."""
    cat = detect_role_category(
        "RTL Design Engineer",
        "Own RTL for the fabric and partner with the physical design team on "
        "floorplan, timing closure and signoff readiness.",
    )
    assert cat == RoleCategory.rtl_design, f"got {cat!r}"


def test_a_verification_role_keeps_its_category_despite_backend_words():
    cat = detect_role_category(
        "Design Verification Engineer",
        "Build UVM testbenches; coordinate with STA and place-and-route owners.",
    )
    assert cat == RoleCategory.design_verification, f"got {cat!r}"
