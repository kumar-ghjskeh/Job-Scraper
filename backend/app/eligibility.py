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


# ── H1B sponsorship signal (curated; Phase 4 → live DOL LCA data) ──────────────
# Defense / government-heavy employers that typically require US-person status.
_NON_SPONSOR = {
    "anduril", "shield ai", "spacex", "lockheed martin", "northrop grumman",
    "general dynamics mission systems", "bae systems", "rtx", "raytheon",
    "l3harris",
}
# Semiconductor / silicon employers known to file many H1B LCAs for EE roles.
_KNOWN_SPONSOR = {
    "nvidia", "amd", "intel", "qualcomm", "marvell", "micron", "nxp semiconductors",
    "analog devices", "broadcom", "arm", "synopsys", "cadence", "siemens eda",
    "cisco", "apple", "google", "microsoft", "meta", "amazon",
    "samsung semiconductor", "western digital", "seagate", "texas instruments",
    "mediatek", "renesas", "infineon technologies", "microchip technology",
    "astera labs", "tenstorrent", "cerebras systems", "sambanova systems",
    "lightmatter", "d-matrix", "etched", "rain ai", "axelera ai", "matx",
    "lemurian labs", "baya systems", "ventana micro systems", "lattice semiconductor",
    "eliyan", "groq", "sifive", "arista networks", "juniper networks", "rambus",
    "credo semiconductor", "maxlinear", "keysight technologies", "synaptics",
}


def sponsors_h1b(company: str) -> Optional[bool]:
    """True = known H1B sponsor, False = typically US-person-only, None = unknown."""
    c = (company or "").lower().strip()
    if c in _NON_SPONSOR:
        return False
    if c in _KNOWN_SPONSOR:
        return True
    return None
