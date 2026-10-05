"""The board shows RTL design and design verification. Nothing else.

role_category alone could not enforce that, because it matched title PLUS
description and chip-company descriptions mention everything. Real failures from the
live corpus before this gate existed:

    "PRINCIPAL RTL DESIGN"                            filed as Pre-Silicon Validation
    "Sr. Engineer, CPU RTL Design"                    filed as Pre-Silicon Validation
    "PD Engineer, Annapurna Labs"                     filed as DFT (it is backend)
    "Principal Product Application Engineer - PCIe"   shown as in scope
    "Technical Chief of Staff for ASIC Engineering"   shown as in scope
    "Staff GenAI Engineer - Silicon Design"           shown as in scope

The gate decides on the TITLE, which states the discipline; the description does not.
Postings out of scope are recategorised, never deleted.
"""

from __future__ import annotations

import re

from backend.app.role_scope import classify_scope, is_rtl_or_dv
from backend.app.scoring import detect_role_category
from backend.app.snapshot import HIDDEN_CATEGORIES

# ── Titles that MUST be in scope. All taken from the live corpus. ───────────────
IN_SCOPE = [
    "RTL Design Engineer",
    "PRINCIPAL RTL DESIGN",
    "Sr. Engineer, CPU RTL Design",
    "Senior Design Verification Engineer",
    "Staff Engineer, Design Verification",
    "ASIC Design Verification Engineer, DFT",   # DV role that covers DFT
    "ASIC Design Engineer - Cache Controller",
    "ASIC Engineer I, Annapurna Labs, Early Career - 2027",
    "AI GPU Cache Designer",
    "ASIC Digital / DSP Design Engineer",
    "Bluespec Design Engineer (Haskell)",
    "ASIC Implementation Engineer, Static Verification",
    "Design Verification Engineering Intern - MS/PhD",
    "Formal Verification Engineer",
    "Emulation Engineer",
    "SoC Verification Engineer",
    "FPGA Engineer",
    "Principal Engineer, Microarchitecture",
    "ASIC Architect",
]

# ── Titles that MUST NOT be in scope, with the category each belongs in. ────────
OUT_OF_SCOPE = {
    "Physical Design Engineer": "Physical Design",
    "PD Engineer, Annapurna Labs": "Physical Design",
    "Senior SoC Power Analysis & Optimization Engineer": "Physical Design",
    "Post-Silicon Validation Engineer": "Post-Silicon Validation",
    "Principal Silicon Validation Engineer, SerDes/PAM4": "Post-Silicon Validation",
    "ASIC Bench Characterization Manager": "Post-Silicon Validation",
    "ASIC DFT Engineer": "DFT",
    "CPU DFT Engineer": "DFT",
    "DFT Architect": "DFT",
    "ASIC/SOC CAD Engineer": "EDA / Verification Tools",
    "ASIC/FPGA Methodology Engineer": "EDA / Verification Tools",
    "ASIC Design Automation Engineer": "EDA / Verification Tools",
    "AI/ML Silicon Verification Solutions Engineer - Tools": "EDA / Verification Tools",
    "ASIC Technology Librarian": "EDA / Verification Tools",
    "Principal Product Application Engineer - PCIe": "Adjacent / Backup",
    "Technical Chief of Staff for ASIC Engineering": "Adjacent / Backup",
    "Staff GenAI Engineer - Silicon Design": "Adjacent / Backup",
    "ASIC Engineer, Performance Architecture and Modeling": "Adjacent / Backup",
    "AI SoC Modeling Engineer, Annapurna Labs": "Adjacent / Backup",
    "Server CPU Hardware Systems Lead": "Adjacent / Backup",
    "2027 Masters ASIC Package Engineering Co-op/Intern": "Adjacent / Backup",
    "Marketing Manager, ASIC": "Adjacent / Backup",
    "Sales Engineer, Silicon": "Adjacent / Backup",
}


def test_rtl_and_dv_titles_are_in_scope():
    missed = [t for t in IN_SCOPE if not is_rtl_or_dv(t)]
    assert not missed, (
        "These are RTL design or design verification roles and were excluded:\n  "
        + "\n  ".join(missed)
    )


def test_other_disciplines_are_out_of_scope_and_correctly_categorised():
    wrong = []
    for title, expected in OUT_OF_SCOPE.items():
        in_scope, category = classify_scope(title)
        if in_scope:
            wrong.append(f"{title!r} was treated as RTL/DV")
        elif category != expected:
            wrong.append(f"{title!r} -> {category!r}, expected {expected!r}")
    assert not wrong, "\n  ".join(["scope errors:"] + wrong)


def test_verification_beats_a_specialisation_named_beside_it():
    """"ASIC Design Verification Engineer, DFT" is a DV role covering DFT, not a DFT
    role. Tier 1 exists to win that case, so the ordering is asserted directly."""
    assert is_rtl_or_dv("ASIC Design Verification Engineer, DFT")
    assert not is_rtl_or_dv("ASIC DFT Engineer")


def test_job_function_words_override_discipline_words():
    """Tier 0. "ASIC Design Automation Engineer" contains "ASIC design" but is CAD;
    "Silicon Verification Solutions Engineer" contains "silicon verification" but is
    a tools role. Without this, both were reported as in scope."""
    for title in ("ASIC Design Automation Engineer",
                  "AI/ML Silicon Verification Solutions Engineer - Tools",
                  "Technical Chief of Staff for ASIC Engineering",
                  "Marketing Manager, ASIC"):
        assert not is_rtl_or_dv(title), f"{title!r} should be out of scope"


def test_the_description_cannot_drag_a_posting_into_or_out_of_scope():
    """The whole reason the gate is title-only."""
    # A DV posting whose description is full of backend words stays DV.
    assert detect_role_category(
        "Design Verification Engineer",
        "coordinate with floorplan, STA and signoff owners on timing closure",
    ) == "Design Verification"
    # A DFT posting whose description is full of DV words stays DFT.
    assert detect_role_category(
        "ASIC DFT Engineer",
        "SystemVerilog UVM testbench functional coverage constrained random",
    ) == "DFT"
    # An RTL posting whose description mentions verification stays RTL Design —
    # this specific pair was filing "PRINCIPAL RTL DESIGN" as verification.
    assert detect_role_category(
        "PRINCIPAL RTL DESIGN",
        "pre-silicon verification, UVM, coverage closure",
    ) == "RTL Design"


def test_out_of_scope_categories_are_all_hidden_by_default():
    """Recategorising only helps if those categories are actually hidden."""
    for category in set(OUT_OF_SCOPE.values()):
        assert category in HIDDEN_CATEGORIES, (
            f"{category!r} is not in HIDDEN_CATEGORIES, so postings routed there "
            "still show on a board that is meant to be RTL and DV only"
        )


def test_nothing_in_scope_is_hidden():
    """The inverse guard: the core categories must not drift into the hidden set."""
    for category in ("RTL Design", "Design Verification", "Formal Verification",
                     "Emulation", "FPGA RTL", "SoC Verification",
                     "CPU/GPU Verification"):
        assert category not in HIDDEN_CATEGORIES, f"{category} must stay visible"


def test_patterns_have_real_word_boundaries():
    """A shell heredoc collapsed \\b into a literal backspace byte three times in
    this project's history, and grep renders that invisibly so the file reads as
    correct. Unbounded, short tokens like 'sta' match inside 'Staff'."""
    from backend.app import role_scope
    patterns = [role_scope._DV_TITLE, role_scope._RTL_WEAK_TITLE,
                role_scope._DV_WEAK_TITLE, role_scope._GENERIC_IC_TITLE]
    patterns += [p for _c, p in role_scope._OUT_OF_SCOPE]
    patterns += [p for _c, p in role_scope._HARD_OUT]
    for p in patterns:
        bad = [c for c in p.pattern if ord(c) < 32]
        assert not bad, f"control characters in pattern: {p.pattern[:60]!r}"
    # And the behavioural consequence.
    assert is_rtl_or_dv("Staff Design Verification Engineer")
    assert not re.search(r"\bsta\b", "Staff", re.I)


# Titles found LEAKING onto the live board after the first version of this gate.
# Each matched an RTL-ish phrase while plainly belonging to another discipline,
# because every positive signal outranked the out-of-scope tier. A bare "X design"
# is now weaker than an explicit discipline, and CAD/EDA/physical-design-verification
# outrank even a strong verification phrase.
LIVE_LEAKS = {
    "ASIC Design STA Engineer": "Physical Design",
    "Digital Physical Design (P&R) Intern": "Physical Design",
    "Experienced Digital Physical Design Engineer": "Physical Design",
    "Physical Design Engineer: Die-to-Die Interface (RTL to GDSII)": "Physical Design",
    "Principal CPU Architect - High-Performance and Physical Design": "Physical Design",
    "Senior DFT Logic Design Engineer": "DFT",
    "ASIC Design-for-Test (DFT) Engineer Intern": "DFT",
    "Principal Digital Engineer (DFT Design)": "DFT",
    "FE RTL Infrastructure - CAD Engineer": "EDA / Verification Tools",
    "CPU Design Methodology Engineer": "EDA / Verification Tools",
    "RTL Tools & Methodology Engineer": "EDA / Verification Tools",
    "Sr. Staff CAD- ASIC Design Verification Agentic Workflow": "EDA / Verification Tools",
    "Staff Physical Design Verification, CAD": "EDA / Verification Tools",
    "Full-Chip Physical Design Verification Engineer": "EDA / Verification Tools",
    "Senior ASIC Design Infrastructure & Methodologies engineer": "EDA / Verification Tools",
    "Sr. Emulation Methodology Engineer": "EDA / Verification Tools",
}


def test_live_leaks_stay_out():
    """Regression for every title that reached the board when the tiers were wrong."""
    wrong = []
    for title, expected in LIVE_LEAKS.items():
        in_scope, category = classify_scope(title)
        if in_scope:
            wrong.append(f"{title!r} is back on the board")
        elif category != expected:
            wrong.append(f"{title!r} -> {category!r}, expected {expected!r}")
    assert not wrong, "\n  ".join(["leaks:"] + wrong)


def test_a_weak_rtl_phrase_does_not_beat_a_named_discipline():
    """The ordering fix, stated as its own rule.

    "ASIC design" in "ASIC Design STA Engineer" is context, not the role. But
    "design verification" in "ASIC Design Verification Engineer, DFT" IS the role.
    Strong verification outranks a discipline; weak RTL does not.
    """
    assert not is_rtl_or_dv("ASIC Design STA Engineer")
    assert is_rtl_or_dv("ASIC Design Verification Engineer, DFT")
    # And with no competing discipline, the weak signal is trusted.
    assert is_rtl_or_dv("ASIC Design Engineer")


def test_cad_outranks_even_a_strong_verification_phrase():
    """Tier 0. "Sr. Staff CAD- ASIC Design Verification Agentic Workflow" contains
    "design verification" but is a CAD role, so CAD has to win."""
    assert not is_rtl_or_dv("Sr. Staff CAD- ASIC Design Verification Agentic Workflow")
    assert not is_rtl_or_dv("Staff Physical Design Verification, CAD")
