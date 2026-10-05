"""Strict scope gate: is this posting RTL design or design verification?

The board is for RTL design and RTL verification only. The role_category taxonomy
could not carry that on its own, because it matched against title PLUS description
and chip-company descriptions mention everything — so it leaked both ways:

    "PRINCIPAL RTL DESIGN"              was filed as Pre-Silicon Validation
    "Sr. Engineer, CPU RTL Design"      was filed as Pre-Silicon Validation
    "PD Engineer, Annapurna Labs"       was filed as DFT (it is Physical Design)
    "Principal Product Application Engineer - PCIe"   counted as in-scope
    "Technical Chief of Staff for ASIC Engineering"   counted as in-scope
    "Staff GenAI Engineer - Silicon Design"           counted as in-scope

Decided on the TITLE ALONE, for the same reason the physical-design split is: the
title states the discipline, the description does not. A DV posting that mentions
floorplanning is still DV; an STA posting that mentions UVM is still not.

Three tiers, in this order, because two-tier ordering cannot express the real cases:

  1. CORE — an explicit RTL or design-verification title. Wins outright, so
     "ASIC Design Verification Engineer, DFT" stays DV: it is a verification role
     that happens to cover DFT, not a DFT role.
  2. OUT — a different discipline is named. Only reached when tier 1 did not match,
     so "ASIC DFT Engineer" (no DV/RTL phrase) lands here correctly.
  3. GENERIC — a bare IC-engineering title such as "ASIC Engineer". In scope, but
     only because tier 2 already ruled out the specialisations. Without this tier
     Amazon's and Annapurna's "ASIC Engineer I" postings — real RTL work — were
     being dropped as unidentifiable.

Anything still unmatched is OUT. Strict means the default is exclusion: a title we
cannot positively identify as RTL or DV does not belong on this board.

Nothing is deleted. Out-of-scope postings get a category the default view hides, so
they stay reachable behind the existing toggle.
"""

from __future__ import annotations

import re

# ── Tier 0: HARD OUT — job functions that are never an RTL/DV engineering role ──
#
# These beat tier 1, because they describe the FUNCTION rather than the discipline
# and the discipline noun beside them is just context. Found by reviewing what the
# three-tier version let through: "ASIC Design Automation Engineer" matched
# "ASIC design" but design automation is CAD, and "AI/ML Silicon Verification
# Solutions Engineer - Tools" matched "silicon verification" but is a tools role.
# Kept deliberately short — every entry here overrides explicit RTL/DV evidence.
_HARD_OUT: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("EDA / Verification Tools", re.compile(
        r"design\s+automation|\bsolutions?\s+engineer\b|\btools?\s+engineer\b"
        r"|\bcad\b|\beda\b|physical\s+design\s+verification"
        r"|\blibrarian\b", re.I)),
    ("Adjacent / Backup", re.compile(
        r"chief\s+of\s+staff|program\s+manage|project\s+manage|product\s+manage"
        r"|technical\s+writer|\bsales\b|\bmarketing\b|recruit|\btalent\b"
        r"|application\s+engineer|field\s+engineer", re.I)),
)

# ── Tier 1: CORE — explicit RTL design or design verification ───────────────────

# Verification first: a title carrying both "design" and "verification" is a
# verification role, and it must outrank any DFT or validation word beside it.
_DV_TITLE = re.compile(
    r"\bdesign\s+verification\b"
    r"|\bverification\s+(engineer|lead|architect|manager|intern|engineering|scientist)\b"
    r"|\bstatic\s+verification\b"
    r"|\b(functional|formal|pre[- ]silicon|hardware|silicon|chip|block|ip|soc|cpu|gpu"
    r"|subsystem|fabric|memory|protocol|coherency|interconnect)\s+verification\b"
    # NOTE: emulation deliberately lives in _DV_WEAK_TITLE, not here. "Emulation"
    # names a technique, not the role: "Sr. Emulation Methodology Engineer" is
    # tooling, and ranking emulation as strong evidence put it on the board.
    r"|\b(systemverilog|system\s+verilog)\b"
    r"|\buvm\b"
    r"|\btestbench\b"
    r"|\bdv\s+(engineer|lead|architect|intern)\b"
    r"|\bverif\b",
    re.I,
)

_RTL_WEAK_TITLE = re.compile(
    r"\brtl\b"
    r"|\b(logic|front[- ]end|frontend)\s+design\b"
    # "ASIC Digital / DSP Design Engineer" — the words are separated, so a literal
    # "digital design" misses it.
    r"|\bdigital\b.{0,20}\bdesign\b"
    r"|\b(asic|soc|chip|vlsi|fpga|cpu|gpu|ip)\s+design\b"
    r"|\bdesign\s+engineer,?\s+(asic|soc|rtl|cpu|gpu|silicon|digital)\b"
    r"|\bmicro[- ]?architect"
    r"|\b(asic|soc|cpu|gpu|chip)\s+architect\b"
    r"|\b(verilog|vhdl|bluespec|chisel|systemc)\b"
    r"|\bfpga\s+(engineer|developer|design)\b"
    r"|\bdigital\s+(ic|circuit)\s+design\b"
    # "AI GPU Cache Designer", "CPU Core Designer" — designer, in a hardware context.
    r"|\b(cache|cpu|gpu|core|logic|digital|chip|soc|asic|pipeline|interconnect)\s+designer\b",
    re.I,
)

# ── Tier 2: OUT — a different discipline, mapped to the category it belongs in ──

_OUT_OF_SCOPE: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Backend implementation. Also caught by scoring._PHYSICAL_DESIGN_TITLE; kept
    # here so this module is correct used on its own.
    ("Physical Design", re.compile(
        r"\bphysical\s+design\b|\bpd\s+engineer\b|\bfloorplan|place\s*(and|&)\s*route"
        r"|\bpnr\b|static\s+timing|\bsta\b|timing\s+(closure|signoff|engineer)"
        r"|\bsignoff\b|\bgds|clock\s+tree|\bcts\b|\bdrc\b|\blvs\b"
        r"|power\s+(integrity|analysis|optimi)|signal\s+integrity", re.I)),
    # After the chip exists: lab and bring-up work, not RTL or DV.
    ("Post-Silicon Validation", re.compile(
        r"post[- ]silicon|silicon\s+validation|system\s+validation|board\s+validation"
        r"|bring[- ]?up|characteri[sz]ation|\bsipi\b|bench\s+(test|characteri)"
        r"|\bate\b|\btest\s+engineer\b|product\s+engineer|failure\s+analysis"
        r"|validation\s+(engineer|lead|manager|director)", re.I)),
    # Design-for-test is its own discipline. Categorised, not discarded.
    ("DFT", re.compile(
        r"\bdft\b|design[- ]for[- ]test|\bscan\s+(insertion|chain)\b|\batpg\b"
        r"|\bmbist\b|\bjtag\b|testability", re.I)),
    # Building the environment rather than designing or verifying a chip.
    ("EDA / Verification Tools", re.compile(
        r"\bcad\b|\beda\b|methodolog|\binfrastructure\b"
        r"|\bflow\s+(engineer|development)\b"
        r"|tool\s*(ing|chain|development)|\bcompiler\b|synthesis\s+engineer"
        r"|layout\s+synthesis|\blibrary\s+characteri", re.I)),
    # Architecture/performance modelling sits upstream of RTL and is a distinct job.
    ("Adjacent / Backup", re.compile(
        r"\bmodeling\b|\bmodelling\b|performance\s+(architect|model|analy)"
        r"|\bsystems?\s+(lead|engineer|architect|design)\b"
        r"|\banalog\b|mixed[- ]signal|\brf\b|radio\s+frequency|\bpackag"
        r"|\blayout\b|\bpcb\b|thermal|mechanical|\bdsp\s+algorithm"
        r"|application\s+engineer|field\s+engineer|solutions?\s+(architect|engineer)"
        r"chief\s+of\s+staff|program\s+manage|project\s+manage|product\s+manage"
        r"|technical\s+writer|\bsales\b|\bmarketing\b|recruit|\btalent\b"
        r"|application\s+engineer|field\s+engineer", re.I)),
)

# ── Tier 3: GENERIC — a bare IC-engineering title, in scope once tier 2 is clear ─

# Verification TECHNIQUES. Real DV signals, but weak ones: they name a method rather
# than the role, so a discipline word beside them should win. Checked at tier 3 with
# the weak RTL signals.
_DV_WEAK_TITLE = re.compile(r"\bemulation\b|\bemulator\b|\bprototyping\b", re.I)

_GENERIC_IC_TITLE = re.compile(
    r"\b(asic|soc|silicon|vlsi)\s+(engineer|engineering)\b"
    r"|\bhardware\s+design\s+engineer\b"
    r"|\bdigital\s+engineer\b",
    re.I,
)


def classify_scope(title: str) -> tuple[bool, str | None]:
    """Return ``(in_scope, out_of_scope_category)``.

    ``in_scope`` is True only for RTL design or design verification. When False, the
    second element names the category the posting belongs in — "Adjacent / Backup"
    when nothing more specific fits.
    """
    t = title or ""
    # Tier 0 — a job function that is never RTL/DV engineering, whatever noun sits
    # beside it. Checked before tier 1 precisely so it can override explicit
    # RTL/DV words used as context ("ASIC Design Automation", "Silicon
    # Verification Solutions Engineer - Tools").
    for category, pattern in _HARD_OUT:
        if pattern.search(t):
            return False, category
    # Tier 1 — a STRONG verification phrase, where verification IS the role. Only
    # this outranks tier 2, which is what keeps "ASIC Design Verification Engineer,
    # DFT" a DV role while "ASIC DFT Engineer" is not.
    if _DV_TITLE.search(t):
        return True, None
    # Tier 2 — a different discipline is named.
    #
    # This deliberately outranks the WEAK RTL signals below. A bare "X design" is
    # not strong evidence: "ASIC Design STA Engineer", "Digital Physical Design
    # (P&R) Intern", "Senior DFT Logic Design Engineer" and "FE RTL Infrastructure -
    # CAD Engineer" all matched an RTL-ish phrase while plainly belonging to another
    # discipline. Ranking every positive above this tier put all four on the board.
    for category, pattern in _OUT_OF_SCOPE:
        if pattern.search(t):
            return False, category
    # Tier 3 — RTL design evidence, and verification techniques, both trustworthy
    # now the specialisations are gone.
    if _RTL_WEAK_TITLE.search(t) or _DV_WEAK_TITLE.search(t):
        return True, None
    # Tier 4 — generic IC engineering.
    if _GENERIC_IC_TITLE.search(t):
        return True, None
    return False, "Adjacent / Backup"


def is_rtl_or_dv(title: str) -> bool:
    """Convenience predicate — True only for RTL design or design verification."""
    return classify_scope(title)[0]
