"""Eligibility / export-control risk detection and H1B sponsorship signal.

- ``detect_eligibility_risk`` scans a job description for citizenship,
  clearance, and export-control language and returns a risk level + the
  human-readable categories that matched.
- ``sponsors_h1b`` returns a company-level H1B sponsorship signal so
  international candidates can prioritize. (Phase 4 will replace the curated
  list with live DOL LCA disclosure data.)
"""

from __future__ import annotations

import re
from typing import Optional

# label -> regex patterns
_HIGH: dict[str, list[str]] = {
    "U.S. citizenship required": [
        r"u\.?\s?s\.?\s?citizen", r"must be a u\.?\s?s\.?\s?citizen",
        r"us citizenship", r"sole u\.?s\.? citizen",
    ],
    "Security clearance required": [
        r"security clearance", r"secret clearance", r"top secret", r"ts/sci",
        r"\bsci\b clearance", r"active clearance", r"polygraph", r"dod clearance",
    ],
}

_MEDIUM: dict[str, list[str]] = {
    "U.S. person / green card": [
        r"u\.?\s?s\.?\s?person", r"green card", r"permanent resident",
        r"lawful permanent resident",
    ],
    "ITAR / export control": [
        r"\bitar\b", r"export[-\s]control", r"\bear\b\s", r"controlled technology",
        r"export administration regulations",
    ],
    "Government / defense work": [
        r"government contract", r"cleared facility", r"defense contract",
    ],
}


def detect_eligibility_risk(text: str) -> tuple[str, list[str]]:
    """Return (risk_level, matched_labels). risk_level ∈ {low, medium, high}."""
    t = (text or "").lower()
    if not t:
        return "low", []

    high = [label for label, pats in _HIGH.items() if any(re.search(p, t) for p in pats)]
    if high:
        return "high", high

    medium = [label for label, pats in _MEDIUM.items() if any(re.search(p, t) for p in pats)]
    if medium:
        return "medium", medium

    return "low", []


# ── H1B sponsorship signal ────────────────────────────────────────────────────
#
# Two bugs lived here. First, this signal is a model @property and was never
# added to snapshot.LIST_FIELDS, so it never reached the corpus — and the app is
# now served from that corpus, so the frontend read `j.sponsors_h1b === false` on
# a field that was always undefined and the H1B filter silently matched EVERY
# job. Second, the lookup was exact set membership on a lowercased name, so
# "cadence" never matched the catalog's "Cadence Design Systems" and "renesas"
# never matched "Renesas Electronics" — both reported unknown. 22 of 54
# producing companies (101 US jobs) fell through that way.
#
# The company signal is a PRIOR, not an answer: it says whether this employer
# files H1B LCAs for engineering roles at all. The posting's own text is
# authoritative and overrides it — see h1b_accessible(). An employer that
# sponsors broadly still posts individual reqs gated on citizenship.
#
# This list is curated and reasoned, not scraped from a filing database. The
# upgrade path is the DOL's public LCA disclosure data, which is free but a few
# hundred MB per quarter; until that is wired in, "unknown" stays visibly
# unknown rather than being quietly treated as a yes.

# Corporate suffixes and category words that differ between how a company names
# itself and how a careers page writes it. Stripped from BOTH sides.
_NOISE = (
    "incorporated", "technologies", "technology", "semiconductors",
    "semiconductor", "design systems", "electronics", "solutions", "systems",
    "microsystems", "corporation", "company", "group", "labs", "inc", "corp",
    "llc", "ltd", "plc", "co", "sa", "nv", "ag",
)


def _norm(name: str) -> str:
    """Comparable form of a company name.

    Both the lookup keys and the query go through this, so "Cadence Design
    Systems", "Cadence" and "cadence design systems, inc." all land on one
    string. The lists below keep the readable full names.
    """
    t = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower())
    for word in _NOISE:
        t = re.sub(r"\b" + re.escape(word) + r"\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Employers that require US-person status for the silicon/FPGA work we surface.
# Defense and aerospace primes do file H1B LCAs for some corporate functions, but
# their RTL/FPGA openings sit on cleared programs, so an H1B candidate cannot
# take them. Marked False deliberately — a false "maybe" costs an application.
_NON_SPONSOR_NAMES = (
    "Lockheed Martin", "Northrop Grumman", "General Dynamics Mission Systems",
    "BAE Systems", "RTX", "Raytheon", "L3Harris", "Anduril", "Shield AI",
    "SpaceX", "Boeing", "Collins Aerospace", "Draper", "MITRE",
    "Sandia National Laboratories", "Johns Hopkins APL", "Aerospace Corporation",
    "Leidos", "SAIC", "Mercury Systems", "Kratos", "Sierra Nevada Corporation",
    # Honeywell sponsors broadly as a company, but the FPGA/RTL openings sit in
    # Aerospace under ITAR, same as Boeing and Collins.
    "Honeywell",
)

# Employers that routinely file H1B LCAs for electrical/hardware engineering,
# grouped by why they qualify so a future reader can judge an addition.
_SPONSOR_NAMES = (
    # Large US semiconductor and EDA employers — long-standing high-volume filers
    # for design and verification roles.
    "NVIDIA", "AMD", "Intel", "Qualcomm", "Marvell", "Micron", "Broadcom",
    "Texas Instruments", "Analog Devices", "Microchip Technology",
    "Synopsys", "Cadence Design Systems", "Siemens EDA", "Keysight Technologies",
    "Teradyne", "Applied Materials", "KLA", "Lattice Semiconductor",
    "Silicon Labs", "Skyworks Solutions", "Qorvo", "Semtech", "onsemi",
    "Cirrus Logic", "MaxLinear", "Rambus", "Allegro MicroSystems",
    "indie Semiconductor", "Ambarella", "Synaptics", "Wolfspeed",
    "Monolithic Power Systems", "SiTime", "Astera Labs", "Credo Semiconductor",
    "Alphawave Semi", "Achronix", "Arteris",
    # Global semiconductor firms with substantial US design sites.
    "Arm", "NXP Semiconductors", "Infineon Technologies", "STMicroelectronics",
    "Renesas Electronics", "MediaTek", "TSMC", "GlobalFoundries",
    "Samsung Semiconductor", "SK Hynix", "Kioxia", "Western Digital", "Sandisk",
    "Seagate", "Imagination Technologies",
    # Big-tech silicon teams.
    "Apple", "Google", "Meta", "Amazon", "Microsoft", "Cisco",
    "Juniper Networks", "Arista Networks", "Tesla", "Waymo", "Nokia", "Ciena",
    "IBM", "Oracle", "ByteDance", "Hewlett Packard Enterprise",
    # Venture-backed silicon startups. These hire heavily out of US graduate
    # programmes, which in practice means cap-exempt-to-cap H1B transfers.
    "Tenstorrent", "Cerebras Systems", "SambaNova Systems", "Groq", "SiFive",
    "Rivos", "Ventana Micro Systems", "Esperanto Technologies", "Ampere Computing",
    "Lightmatter", "Ayar Labs", "Celestial AI", "Enfabrica", "d-Matrix",
    "Etched", "MatX", "Eliyan", "Baya Systems", "Axiado", "Mythic", "Ambiq",
    "SiMa.ai", "Untether AI", "Expedera", "Quadric", "Blaize", "Recogni",
    "Cornelis Networks", "Tetramem", "Axelera AI", "Rain AI", "Lemurian Labs",
    "Recogni (Tensordyne)", "Tensordyne",
    "Graphcore", "Normal Computing", "Flex Logix", "Nubis Communications",
    "Lumotive", "EnCharge AI", "Kinara", "Hailo", "FuriosaAI", "Ethernovia",
    # Quantum and photonics — US-based, academic-pipeline hiring.
    "PsiQuantum", "Atom Computing", "IonQ", "Rigetti Computing", "QuEra Computing",
    "Infleqtion", "Quantinuum", "Xanadu",
)

_NON_SPONSOR = {_norm(n) for n in _NON_SPONSOR_NAMES}
_KNOWN_SPONSOR = {_norm(n) for n in _SPONSOR_NAMES}

# Eligibility levels that block an H1B candidate whatever the employer. "medium"
# covers green-card / US-person wording and ITAR, each of which rules an H1B
# holder out as firmly as an explicit citizenship demand.
_H1B_BLOCKING_RISK = frozenset({"high", "medium"})


def sponsors_h1b(company: str) -> Optional[bool]:
    """True = known H1B sponsor, False = typically US-person-only, None = unknown."""
    c = _norm(company)
    if not c:
        return None
    if c in _NON_SPONSOR:
        return False
    if c in _KNOWN_SPONSOR:
        return True
    return None


def h1b_accessible(company: str, eligibility_risk: str | None) -> bool:
    """Can an H1B candidate actually apply to this specific posting?

    Strict by design: the requirement is that the H1B filter show only jobs and
    companies that sponsor. So an unknown employer is NOT a yes, and a known
    sponsor's posting still fails when its own text demands citizenship, a green
    card, or ITAR-controlled access.
    """
    if sponsors_h1b(company) is not True:
        return False
    return (eligibility_risk or "low").lower() not in _H1B_BLOCKING_RISK
