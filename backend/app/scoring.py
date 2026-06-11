"""Match scoring, job classification, and experience-level detection."""

from __future__ import annotations

import json
import re
from typing import Optional

from .config import load_keywords
from .models import ExperienceLevel, RemoteStatus, RoleCategory

_kw = load_keywords()


# ── Score labels ──────────────────────────────────────────────────────────────

def score_to_label(score: int) -> str:
    if score >= 85:
        return "Excellent Fit"
    if score >= 75:
        return "Strong Fit"
    if score >= 65:
        return "Good Fit"
    if score >= 50:
        return "Possible Fit"
    return "Low Fit"


# ── Software-only detection ───────────────────────────────────────────────────

_SOFTWARE_ONLY_TITLE_PATTERNS = [
    r"\bsoftware\s+development\s+engineer\b",
    r"\bsde\b",
    r"\bbackend\s+engineer\b",
    r"\bfrontend\s+engineer\b",
    r"\bfull.?stack\b",
    r"\bcloud\s+software\b",
    r"\bml\s+compiler\b",
    r"\bcompiler\s+engineer\b",
    r"\bsite\s+reliability\b",
    r"\bdevops\b",
    r"\bdata\s+engineer\b",
    r"\bplatform\s+engineer\b",
    r"\binfrastructure\s+engineer\b",
    r"\bapi\s+engineer\b",
    r"\bweb\s+engineer\b",
    r"\bpython\s+engineer\b",
    r"\bkubernetes\b",
    r"\bmicroservices\b",
]

_HW_OVERLAP_SIGNALS = [
    "hardware", "rtl", "asic", "verification", "fpga", "silicon", "soc",
    "uvm", "systemverilog", "verilog", "pre-silicon", "emulation", "dft",
    "cpu", "gpu", "microarchitecture", "digital design", "logic design",
    "ip design", "subsystem", "memory controller", "pcie", "cxl", "axi",
    "amba", "risc", "hdl", "vhdl",
]

_CODESIGN_SIGNALS = [
    "co-design", "codesign", "hardware/software", "hw/sw",
    "hardware software", "hw sw", "firmware",
]


def is_software_only(title: str, description: str = "") -> bool:
    """True if job is purely software with no hardware overlap."""
    title_l = title.lower()
    desc_l = description.lower()
    combined = title_l + " " + desc_l

    # Must have a software-only title pattern
    has_sw_title = any(
        re.search(p, title_l) for p in _SOFTWARE_ONLY_TITLE_PATTERNS
    )
    if not has_sw_title:
        return False

    # If there's any hardware overlap signal, it's NOT software-only
    has_hw = any(sig in combined for sig in _HW_OVERLAP_SIGNALS)
    return not has_hw


# ── Precise RTL / DV relevance gate ───────────────────────────────────────────
# Used to keep the job pool unambiguous: a posting is only stored if it is a
# genuine RTL Design / Design Verification (or directly adjacent silicon) role.

# Strong hardware-design / verification signals (title-level → instantly relevant)
_RELEVANT_TITLE_SIGNALS = [
    "rtl", "asic", "soc", "fpga", "vlsi", "verilog", "systemverilog", "vhdl",
    "design verification", "verification engineer", "dv engineer",
    "digital design", "logic design", "physical design", "microarchitecture",
    "silicon design", "silicon engineer", "hardware design", "hardware engineer",
    "design engineer", "dft", "place and route", "synthesis", "uvm",
    "soc design", "chip design", "ip design", "cpu design", "gpu design",
    "emulation", "formal verification", "pre-silicon", "post-silicon",
    "circuit design", "design for test", "timing", "pd engineer",
]

# Role-specific methodology signals (NOT generic company boilerplate like
# "asic"/"soc"/"silicon" which appears in every chip-company JD). A title-less
# posting must hit several of these to count as relevant.
_RELEVANT_DESC_SIGNALS = [
    "systemverilog", "uvm", "verilog", "vhdl", "rtl design", "rtl coding",
    "testbench", "design verification", "functional coverage", "constrained random",
    "logic synthesis", "timing closure", "physical design", "place and route",
    "logic design", "microarchitecture", "design for test", "scan insertion",
    "atpg", "formal property", "formal verification", "clock domain crossing",
    "register transfer level", "hdl", "synthesizable", "lint ", "cdc ",
]

# Titles that are never relevant regardless of body keywords:
# non-engineering roles, plus analog/layout/optical/firmware (out of RTL/DV scope).
_HARD_EXCLUDE_TITLE = [
    # Non-engineering
    r"\bsales\b", r"\bmarketing\b", r"\brecruit", r"\bhuman resources\b", r"\bhr\b",
    r"\baccountant\b", r"\baccounting\b", r"\bfinance\b", r"\bfinancial\b",
    r"\blegal\b", r"\bcounsel\b", r"\bparalegal\b", r"\bsupply chain\b",
    r"\blogistics\b", r"\bprocurement\b", r"\bsourcing\b", r"\bbuyer\b",
    r"\bfacilities\b", r"\bbenefits\b", r"\bpayroll\b", r"\btalent\b",
    r"\bcustomer success\b", r"\baccount manager\b", r"\baccount executive\b",
    r"\bbusiness development\b", r"\bprogram manager\b", r"\bproject manager\b",
    r"\bproduct manager\b", r"\bproduct marketing\b", r"\boperations manager\b",
    r"\bpeople\b", r"\boffice manager\b", r"\badministrator\b", r"\badministrative\b",
    r"\btechnical writer\b", r"\bmechanical\b", r"\bthermal\b", r"\bmaterials\b",
    r"\bchemist\b", r"\bbiolog", r"\bnurse\b", r"\bdriver\b", r"\btechnician\b",
    # Pure software
    r"\bdata scientist\b", r"\bdata engineer\b", r"\bweb developer\b",
    r"\bfront.?end\b", r"\bback.?end\b", r"\bfull.?stack\b", r"\bdevops\b",
    r"\bsite reliability\b", r"\bsalesforce\b", r"\bit support\b", r"\bhelpdesk\b",
    r"\bgraphic design\b", r"\bux\b", r"\bui/ux\b",
    # Out-of-scope hardware specialties (analog / layout / optical / packaging)
    r"\banalog\b", r"\bmixed.?signal\b", r"\blayout engineer\b", r"\brf engineer\b",
    r"\bphotonic", r"\boptical\b", r"\bpackaging\b", r"\bsubstrate\b",
    r"\bpower amplifier\b", r"\bdevice engineer\b", r"\bprocess engineer\b",
    r"\byield\b", r"\bfailure analysis\b", r"\bsignal integrity\b",
    r"\bpower electronics\b", r"\bboard design\b", r"\bpcb\b",
]

# Digital RTL/DV title signals that are decisive on their own.
_DIGITAL_TITLE_SIGNALS = [
    "rtl", "asic", "soc", "fpga", "vlsi", "verilog", "systemverilog", "vhdl",
    "design verification", "verification engineer", "dv engineer", "digital design",
    "logic design", "physical design", "microarchitecture", "silicon design",
    "hardware design", "soc design", "chip design", "ip design", "cpu",
    "gpu", "emulation", "formal verification", "pre-silicon", "post-silicon",
    "dft", "design for test", "synthesis", "place and route", "pd engineer",
]


def is_rtl_dv_relevant(title: str, description: str = "") -> tuple[bool, str]:
    """Decide whether a posting is a genuine RTL/DV (or adjacent digital silicon)
    role. Returns (is_relevant, reason). Title-first, so it works even when a
    scraper provides no description (e.g. Workday list endpoints)."""
    title_l = title.lower()
    desc_l = description.lower()

    # 1. Hard title exclusions (non-eng, software, analog/layout/optical)
    for pat in _HARD_EXCLUDE_TITLE:
        if re.search(pat, title_l):
            return False, "Excluded role (out of RTL/DV scope)"

    # 2. Pure-software role with no hardware overlap
    if is_software_only(title, description):
        return False, "Pure software role (no hardware overlap)"

    # 3. Decisive digital RTL/DV title signal → relevant. Word-boundary matched
    #    so short tokens ("soc", "rtl") don't match inside words like "Social".
    for sig in _DIGITAL_TITLE_SIGNALS:
        if re.search(r"\b" + re.escape(sig) + r"\b", title_l):
            return True, f"RTL/DV title signal: {sig}"

    # 4. Generic 'verification'/'validation'/'design engineer' title that is
    #    explicitly hardware-flavoured in title or body.
    if re.search(r"\bverification\b|\bvalidation\b|\bdesign engineer\b", title_l):
        if any(s in (title_l + " " + desc_l) for s in [
            "systemverilog", "uvm", "verilog", "rtl", "testbench", "hdl",
            "digital design", "logic design", "asic", "fpga",
        ]):
            return True, "Hardware design/verification role"

    # 5. No title signal — require an engineering-ish title AND multiple distinct
    #    role-specific signals, so verbose company boilerplate ("we build SoCs")
    #    can never leak non-engineering roles (e.g. "Social Media Lead",
    #    "Mission Operations Director") into the pool.
    eng_title = any(w in title_l for w in [
        "engineer", "designer", "architect", "verification", "design",
        "silicon", "hardware", "rtl", "asic", "vlsi", "soc", "fpga", "dft",
        "member of technical staff", "mts", "cad", "co-op", "intern",
    ])
    hits = [s for s in _RELEVANT_DESC_SIGNALS if s in desc_l]
    if eng_title and len(hits) >= 2:
        return True, "Engineering role with multiple RTL/DV methodology signals"

    return False, "No RTL/DV signal in title or description"


def is_hardware_software_codesign(title: str, description: str = "") -> bool:
    """True if job is HW/SW co-design (adjacent, not pure RTL/DV)."""
    title_l = title.lower()
    combined = title_l + " " + description.lower()

    # Explicit title signal always wins
    if any(sig in title_l for sig in ["co-design", "codesign", "hardware/software", "hw/sw", "hw sw"]):
        return True

    # Description-level co-design with no dominant RTL focus
    if not any(sig in combined for sig in _CODESIGN_SIGNALS):
        return False
    has_strong_rtl = any(sig in combined for sig in [
        "uvm", "systemverilog", "pre-silicon", "testbench"
    ])
    return not has_strong_rtl


# ── Role family classification flags ─────────────────────────────────────────

_DV_TITLE_TERMS = [
    "design verification", "verification engineer", "dv engineer",
    "asic verification", "silicon verification", "digital verification",
    "silicon design verification", "hardware design verification",
    "hardware verification", "asic design verification",
    "soc design verification", "uvm verification",
    "systemverilog verification", "ip verification", "subsystem verification",
]

_DV_DESC_TERMS = [
    "uvm", "systemverilog", "sva", " svb ", "constrained random",
    "functional coverage", "assertions", "testbench", "scoreboard",
    "coverage closure", "verification ip", " vip ", "regression suite",
    "pre-silicon verification", "directed test", "formal property",
]

_RTL_TITLE_TERMS = [
    "rtl design", "rtl engineer", "digital design", "logic design",
    "asic design", "soc design", "asic rtl", "digital design engineer",
    "microarchitecture", "logic design engineer", "vhdl engineer",
]

_RTL_DESC_TERMS = [
    "rtl coding", "verilog", "systemverilog rtl", "vhdl", "synthesis",
    "timing closure", "cdc", "reset domain crossing", "microarchitecture",
    "logic synthesis", "rtl implementation",
]

_SOC_TERMS = [
    "soc verification", "soc design", "subsystem", "ip verification",
    "cache coherence", "memory controller", "noc", "axi", "amba", "pcie",
    "cxl", "risc-v", "arm core", "interconnect",
]

_CPU_GPU_TERMS = [
    "cpu verification", "gpu verification", "cpu design", "gpu design",
    "processor verification", "core verification", "out-of-order",
    "branch prediction", "cache", "tlb", "pipeline",
]

_FPGA_TERMS = [
    "fpga", "fpga design", "fpga verification", "vivado", "quartus",
    "fpga rtl", "fpga prototyping", "hls",
]

_FORMAL_TERMS = [
    "formal verification", "property checking", "jasper", "vc formal",
    "questa formal", "symbiyosys", "jaspergold", "model checking",
    "bounded model", "sva formal",
]

_EMULATION_TERMS = [
    "emulation", "palladium", "zebu", "veloce", "fpga prototype",
    "hardware emulator", "emulation platform", "virtual prototype",
]

_PRE_SILICON_TERMS = [
    "pre-silicon", "pre silicon", "pre-silicon verification",
    "pre-silicon validation", "silicon bring-up", "tape-out",
]

_POST_SILICON_TERMS = [
    "post-silicon", "post silicon", "silicon validation",
    "hardware validation", "bring-up", "debug lab", "jtag",
]

_VALIDATION_TERMS = [
    "hardware validation", "silicon validation", "platform validation",
    "system validation", "functional validation",
]

_DFT_TERMS = [
    "dft", "design for test", "design-for-test", "scan insertion",
    "atpg", "bist", "boundary scan", "jtag dft",
]

_EDA_TERMS = [
    "eda", "eda application", "cad engineer", "cad/cae", "eda tools",
    "electronic design automation", "simulation tool", "synthesis tool",
]


def classify_role_flags(title: str, description: str = "") -> dict[str, bool]:
    """Return a dict of boolean role flags for a job."""
    t = title.lower()
    d = description.lower()
    c = t + " " + d

    sw_only = is_software_only(title, description)
    codesign = is_hardware_software_codesign(title, description)

    is_dv = (
        any(kw in t for kw in _DV_TITLE_TERMS)
        or any(kw in c for kw in _DV_DESC_TERMS)
        or (any(kw in c for kw in ["verification", "testbench", "uvm", "coverage"]) and not sw_only)
    )
    is_rtl = (
        any(kw in t for kw in _RTL_TITLE_TERMS)
        or any(kw in c for kw in _RTL_DESC_TERMS)
        or ("rtl" in c and not sw_only)
    )
    is_soc = any(kw in c for kw in _SOC_TERMS)
    is_cpu_gpu = any(kw in c for kw in _CPU_GPU_TERMS)
    is_fpga = any(kw in c for kw in _FPGA_TERMS)
    is_formal = any(kw in c for kw in _FORMAL_TERMS)
    is_emulation = any(kw in c for kw in _EMULATION_TERMS)
    is_pre_silicon = any(kw in c for kw in _PRE_SILICON_TERMS)
    is_post_silicon = any(kw in c for kw in _POST_SILICON_TERMS)
    is_validation = any(kw in c for kw in _VALIDATION_TERMS)
    is_dft = any(kw in c for kw in _DFT_TERMS)
    is_eda = any(kw in c for kw in _EDA_TERMS)

    return {
        "is_design_verification": is_dv and not sw_only,
        "is_rtl_design": is_rtl and not sw_only,
        "is_soc_verification": is_soc and not sw_only,
        "is_cpu_gpu_verification": is_cpu_gpu and not sw_only,
        "is_fpga": is_fpga and not sw_only,
        "is_formal": is_formal,
        "is_emulation": is_emulation,
        "is_pre_silicon": is_pre_silicon,
        "is_post_silicon": is_post_silicon,
        "is_validation": is_validation,
        "is_dft": is_dft,
        "is_eda_tools": is_eda,
        "is_software_only": sw_only,
        "is_hardware_software_codesign": codesign,
    }


def role_flags_to_json(flags: dict[str, bool]) -> str:
    return json.dumps(flags)


# ── Main scoring function ─────────────────────────────────────────────────────

def calculate_match_score(
    job_title: str,
    description: str,
    company_priority: str,
    location: str,
    is_usa: bool = False,
    first_seen_recently: bool = False,
    ats_platform: str = "",
) -> tuple[int, list[str], dict[str, int]]:
    """Return (score 0-100, matched keywords list, breakdown dict)."""

    score = 0
    matched: list[str] = []
    breakdown: dict[str, int] = {}

    title_l = job_title.lower()
    desc_l = description.lower()
    combined = title_l + " " + desc_l

    def add(reason: str, pts: int, kw: Optional[str] = None) -> None:
        nonlocal score
        score += pts
        breakdown[reason] = breakdown.get(reason, 0) + pts
        if kw and kw not in matched:
            matched.append(kw)

    # ── Software-only penalty first ───────────────────────────────────────────
    if is_software_only(job_title, description):
        add("Pure software role (no HW overlap)", -40)
        return max(0, min(100, score)), matched, breakdown

    # ── Positive signals ──────────────────────────────────────────────────────

    # +30  title strongly matches DV / Verification / UVM / SystemVerilog
    dv_title = [
        "design verification", "verification engineer", "uvm", "systemverilog",
        "asic verification", "silicon verification", "digital verification",
        "hardware verification", "dv engineer",
    ]
    for kw in dv_title:
        if kw in title_l:
            add("DV/Verification title keyword", 30, kw)
            break

    # +25  title contains RTL / ASIC / SoC / CPU / GPU / FPGA / IP
    rtl_title = [
        "rtl", "asic", "soc", "cpu", "gpu", "fpga", "digital design",
        "logic design", "microarchitecture",
    ]
    for kw in rtl_title:
        if kw in title_l:
            add("RTL/ASIC/SoC title keyword", 25, kw)
            break

    # +20  description contains deep technical keywords
    desc_tech = [
        "systemverilog", "uvm", "sva", "constrained random", "functional coverage",
        "assertions", "verilog", "formal verification", "emulation",
        "testbench", "coverage closure", "verification ip",
    ]
    for kw in desc_tech:
        if kw in desc_l:
            add("Technical skills in description", 20, kw)
            break

    # +20  entry-level / new-grad explicit signals
    entry_kws_plain = [
        "new grad", "new-grad", "entry level", "entry-level", "early career",
        "0-1 year", "0-2 year", "0-3 year", "0 to 1", "0 to 2", "0 to 3",
        "university grad", "recent graduate", "graduate engineer",
        "junior engineer", "associate engineer",
    ]
    _entry_hit = any(kw in combined for kw in entry_kws_plain) or bool(
        re.search(r"\bengineer\s+[i1]\b", combined)
    )
    if _entry_hit:
        add("Entry-level / New Grad signal", 20, "entry-level")

    # +15  confirmed USA location
    if is_usa:
        add("USA location confirmed", 15, "USA")
    else:
        usa_sigs = ["usa", "united states", "remote", " ca,", " tx,", " wa,", " ny,", " ma,"]
        loc_l = location.lower()
        for sig in usa_sigs:
            if sig in loc_l:
                add("USA location signal", 10, "USA")
                break

    # +10  high-priority company
    if company_priority in ("S", "A"):
        add("S/A-tier company", 10, f"priority-{company_priority}")

    # +10  recent posting (first seen within 24h)
    if first_seen_recently:
        add("Posted recently (< 24h)", 10, "recent")

    # +5  transparent ATS
    if ats_platform in ("greenhouse", "lever", "ashby"):
        add("Transparent ATS (reliable apply link)", 5)

    # ── Penalties ─────────────────────────────────────────────────────────────

    # −35  seniority in title
    senior_title = [
        "senior", " staff ", "principal", "director", "architect",
        "manager", " vp ", "lead ", "distinguished",
    ]
    for kw in senior_title:
        if kw in f" {title_l} ":
            add("Senior/Staff/Principal in title", -35)
            break

    # −30  requires 5+ years
    if re.search(r"\b([5-9]|\d{2,})\+?\s*years?\s*(of\s+)?experience", combined):
        add("Requires 5+ years experience", -30)

    # −25  pure analog / RF
    if re.search(r"\b(analog|rf |mixed.signal|layout engineer|power amplifier)\b", title_l):
        add("Pure analog/RF role", -25)

    # −25  non-USA confirmed
    if not is_usa and location.strip() and location.lower() not in ("", "remote", "worldwide"):
        from .location_utils import parse_location
        loc_result = parse_location(location)
        if loc_result.confidence > 0.8 and not loc_result.is_usa:
            add("Non-USA location", -25)

    return max(0, min(100, score)), matched, breakdown


def score_breakdown_json(breakdown: dict[str, int]) -> str:
    return json.dumps(breakdown)


# ── Classification helpers ─────────────────────────────────────────────────────

def detect_role_category(title: str, description: str = "") -> str:
    """Expanded role category detection using both title and description signals."""
    t = title.lower()
    d = description.lower()
    c = t + " " + d

    # Software-only → not RTL/DV
    if is_software_only(title, description):
        return "Software / Compiler"

    # Priority order: most specific first
    dv_signals = [
        "design verification", "dv engineer", "asic verification",
        "silicon verification", "digital verification", "hardware verification",
        "hardware design verification", "silicon design verification",
        "uvm verification", "systemverilog verification",
        # Description-based DV
        "uvm", "testbench", "functional coverage", "constrained random",
        "coverage closure", "verification ip",
    ]
    if any(sig in c for sig in dv_signals):
        return RoleCategory.design_verification

    if any(sig in c for sig in ["cpu verification", "gpu verification"]):
        return RoleCategory.cpu_gpu_verification

    if any(sig in c for sig in ["soc verification", "subsystem verification", "ip verification"]):
        return RoleCategory.soc_verification

    if any(sig in c for sig in _FORMAL_TERMS):
        return RoleCategory.formal_verification

    if any(sig in c for sig in _EMULATION_TERMS):
        return RoleCategory.emulation

    if any(sig in c for sig in _PRE_SILICON_TERMS):
        return RoleCategory.pre_silicon

    if any(sig in c for sig in _POST_SILICON_TERMS) or any(sig in c for sig in _VALIDATION_TERMS):
        return RoleCategory.post_silicon

    if any(sig in c for sig in _FPGA_TERMS):
        return RoleCategory.fpga_rtl

    rtl_signals = [
        "rtl design", "rtl engineer", "digital design", "logic design",
        "asic design", "soc design", "microarchitecture", "asic rtl",
        "rtl coding", "verilog", "vhdl",
    ]
    if any(sig in c for sig in rtl_signals):
        return RoleCategory.rtl_design

    if any(sig in c for sig in _DFT_TERMS):
        return "DFT"

    if any(sig in c for sig in _EDA_TERMS):
        return RoleCategory.eda_tools

    # Use config mapping as fallback
    mapping = _kw.get("role_category_mapping", {})
    for category, keywords in mapping.items():
        for kw in keywords:
            if kw in c:
                return category

    # Title-level fallback for description-less postings (e.g. Workday list
    # endpoints return titles only). Keep the dashboard from showing "Unknown".
    if "verification" in t or "validation" in t:
        return RoleCategory.design_verification
    if any(s in t for s in [
        "rtl", "asic", "soc", "silicon", "digital design", "logic design",
        "physical design", "hardware design", "chip design", "microarchitecture",
        "ip design", "design engineer", "hardware engineer",
    ]):
        return RoleCategory.rtl_design
    if "cpu" in t or "gpu" in t or "processor" in t:
        return RoleCategory.cpu_gpu_verification
    if "fpga" in t:
        return RoleCategory.fpga_rtl

    return RoleCategory.unknown


def detect_experience_level(title: str, description: str = "") -> str:
    combined = (title + " " + description).lower()

    # New-grad (most specific)
    new_grad_kws = [
        "new grad", "new-grad", "university grad", "recent graduate",
        "graduate engineer", "university graduate",
    ]
    if any(kw in combined for kw in new_grad_kws):
        return ExperienceLevel.new_grad

    # 0-N year range signals
    if any(kw in combined for kw in [
        "0-1 year", "0-2 year", "0-3 year", "0 to 1", "0 to 2", "0 to 3",
        "0-1 years", "0-2 years", "0-3 years",
    ]):
        return ExperienceLevel.zero_to_three

    # Explicit entry-level
    entry_kws = [
        "entry level", "entry-level", "early career", "junior engineer",
        "associate engineer",
    ]
    if any(kw in combined for kw in entry_kws):
        return ExperienceLevel.entry_level

    if re.search(r"\bengineer\s+[i1]\b", combined):
        return ExperienceLevel.entry_level

    # "Hardware Engineer I", "Silicon Engineer I", "ASIC Engineer I"
    if re.search(r"\b\w+\s+engineer\s+i\b", combined):
        return ExperienceLevel.entry_level

    # Senior
    if re.search(r"\b(senior|sr\b|principal|lead\b|director|architect|manager|distinguished)\b", combined):
        return ExperienceLevel.senior

    # Mid-level by years
    if re.search(r"\b([4-9]|\d{2,})\+?\s*years?\b", combined):
        return ExperienceLevel.mid_level

    return ExperienceLevel.unknown


def classify_seniority(title: str, description: str = "") -> tuple[str, int]:
    """Granular seniority classification with a confidence score (0-100).

    Returns one of: New Grad, Entry Level, Junior, Associate, Mid-Level,
    Senior, Staff, Principal, Lead, Manager, Unknown.
    Title signals are high-confidence; years-of-experience inference is medium;
    a bare guess is low. This is more precise than the legacy buckets and is
    what the UI shows + filters on.
    """
    t = title.lower()
    c = (title + " " + description).lower()

    # ── Title-explicit signals (most senior wins) ──
    if re.search(r"\b(manager|director|head of|vice president)\b", t) or re.search(r"\bvp\b", t):
        return "Manager", 95
    if re.search(r"\b(principal|distinguished|fellow)\b", t):
        return "Principal", 95
    if re.search(r"\bstaff\b", t):
        return "Staff", 94
    if re.search(r"\b(tech(nical)? lead|\blead\b)\b", t):
        return "Lead", 88
    if re.search(r"\b(senior|sr\.?)\b", t):
        return "Senior", 92
    if re.search(r"\b(new\s+grad|new\s+college\s+grad|recent\s+graduate|university\s+grad(uate)?|early\s+career|campus)\b", c):
        return "New Grad", 92
    if re.search(r"\bassociate\b", t):
        return "Associate", 84
    if re.search(r"\b(junior|jr\.?)\b", t):
        return "Junior", 86
    if re.search(r"\bentry[\s-]level\b", c):
        return "Entry Level", 86
    if re.search(r"\bengineer\s+(i|1)\b", t) or re.search(r"\b\w+\s+engineer\s+i\b", t):
        return "Entry Level", 80
    if re.search(r"\bengineer\s+(ii|2)\b", t):
        return "Mid-Level", 78

    # ── Years-of-experience inference (medium confidence) ──
    ymin, _ = detect_years_required(c)
    if ymin is not None:
        if ymin >= 8:
            return "Principal", 68
        if ymin >= 5:
            return "Senior", 74
        if ymin >= 3:
            return "Mid-Level", 70
        if ymin <= 2:
            return "Entry Level", 66
    if re.search(r"\b0[\s-]?(to|-)[\s-]?[123]\b|\b0-[123]\s*year", c):
        return "Entry Level", 72

    # ── Description-only new-grad hints (low-medium) ──
    if re.search(r"\b(graduate engineer|associate engineer|junior engineer)\b", c):
        return "Entry Level", 60

    return "Unknown", 30


def classify_seniority_flags(title: str, description: str = "") -> tuple[bool, bool]:
    """Return (is_entry_level, is_senior)."""
    exp = detect_experience_level(title, description)
    is_entry = exp in (ExperienceLevel.new_grad, ExperienceLevel.entry_level, ExperienceLevel.zero_to_three)
    is_senior = exp == ExperienceLevel.senior

    # Title senior signals override
    title_l = title.lower()
    if re.search(r"\b(senior|sr\b|principal|staff\b|lead\b|director|architect|manager|distinguished)\b", title_l):
        is_senior = True
        is_entry = False

    # High year requirements (5+) are effectively senior
    ymin, _ = detect_years_required(title + " " + description)
    if ymin is not None and ymin >= 5:
        is_senior = True
        is_entry = False

    return is_entry, is_senior


def is_candidate_friendly_job(
    job_title: str, description: str, company_priority: str, ats_platform: str
) -> bool:
    """
    True if job is likely friendly for entry-level candidates even without explicit signals.
    Conditions: no seniority signals, strong RTL/DV relevance, S/A company.
    """
    if is_software_only(job_title, description):
        return False

    title_l = job_title.lower()
    if re.search(
        r"\b(senior|sr\b|principal|staff\b|lead\b|director|architect|manager|5\+|7\+|10\+|distinguished)\b",
        title_l,
    ):
        return False

    hw_signals = [
        "verification", "rtl", "asic", "soc", "fpga", "digital design",
        "logic design", "uvm", "systemverilog",
    ]
    has_rtl = any(kw in title_l for kw in hw_signals)

    # Check years in description
    ymin, _ = detect_years_required(description)
    if ymin is not None and ymin >= 4:
        return False

    return has_rtl and company_priority in ("S", "A")


def detect_years_required(text: str) -> tuple[Optional[int], Optional[int]]:
    range_match = re.search(r"(\d+)\s*[-–to]+\s*(\d+)\s*years?", text.lower())
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))
    plus_match = re.search(r"(\d+)\+\s*years?", text.lower())
    if plus_match:
        return int(plus_match.group(1)), None
    single = re.search(r"(\d+)\s*years?\s*(of\s+)?experience", text.lower())
    if single:
        n = int(single.group(1))
        return n, n
    return None, None


def detect_remote_status(location: str, description: str = "") -> str:
    combined = (location + " " + description).lower()
    if "remote" in combined and "hybrid" not in combined:
        return RemoteStatus.remote
    if "hybrid" in combined:
        return RemoteStatus.hybrid
    if location.strip():
        return RemoteStatus.onsite
    return RemoteStatus.unknown


def normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[-,|]\s*(remote|hybrid|onsite|new\s*grad|entry.level)\s*$", "", t)
    t = re.sub(r"\s*\((remote|hybrid|new\s*grad|entry.level)[^)]*\)", "", t)
    return re.sub(r"\s+", " ", t).strip()


def build_relevance_reason(title: str, description: str, breakdown: dict[str, int]) -> str:
    """Build a human-readable relevance reason string."""
    pos = [k for k, v in breakdown.items() if v > 0]
    neg = [k for k, v in breakdown.items() if v < 0]
    parts = []
    if pos:
        parts.append("Matched: " + "; ".join(pos[:3]))
    if neg:
        parts.append("Penalties: " + "; ".join(neg[:2]))
    return ". ".join(parts)
