"""Resume parsing for VLSI candidates.

Extracts text from PDF / DOCX / TXT / TeX and turns it into a structured
profile (skills, tools, protocols, HDLs, methodologies, projects, education,
experience, role focus) using a deterministic VLSI dictionary — no third-party
AI, the resume never leaves this backend.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field, asdict

# ── VLSI skill dictionaries (canonical -> match patterns) ─────────────────────
# Patterns are matched case-insensitively as whole-ish tokens.

HDLS = {
    "Verilog": [r"\bverilog\b"],
    "SystemVerilog": [r"\bsystem\s?verilog\b", r"\bsv\b"],
    "VHDL": [r"\bvhdl\b"],
    "Chisel": [r"\bchisel\b"],
}

METHODOLOGIES = {
    "UVM": [r"\buvm\b", r"universal verification methodology"],
    "OVM": [r"\bovm\b"],
    "SVA": [r"\bsva\b", r"systemverilog assertions", r"\bassertions?\b"],
    "Functional Coverage": [r"functional coverage", r"coverage closure"],
    "Constrained Random": [r"constrained[\s-]?random"],
    "Scoreboard": [r"\bscoreboard\b"],
    "Testbench": [r"\btest\s?bench(es)?\b"],
    "Regression": [r"\bregression\b"],
    "Formal Verification": [r"formal verification", r"property checking", r"equivalence checking"],
    "Gate-Level Sim": [r"gate[\s-]?level", r"\bgls\b"],
    "Emulation": [r"\bemulation\b", r"\bpalladium\b", r"\bzebu\b", r"\bveloce\b"],
}

TOOLS = {
    "VCS": [r"\bvcs\b"], "Verdi": [r"\bverdi\b"], "Xcelium": [r"\bxcelium\b"],
    "Questa": [r"\bquesta\b"], "ModelSim": [r"\bmodelsim\b"], "Incisive": [r"\bincisive\b"],
    "JasperGold": [r"\bjasper\s?gold\b", r"\bjasper\b"], "VC Formal": [r"\bvc formal\b"],
    "Design Compiler": [r"design compiler", r"\bdc\b synthesis"], "Genus": [r"\bgenus\b"],
    "PrimeTime": [r"\bprime\s?time\b"], "Innovus": [r"\binnovus\b"], "ICC2": [r"\bicc2?\b"],
    "SpyGlass": [r"\bspy\s?glass\b"], "Tessent": [r"\btessent\b"], "DFTMAX": [r"\bdftmax\b"],
    "Vivado": [r"\bvivado\b"], "Quartus": [r"\bquartus\b"], "Vverilator": [r"\bverilator\b"],
    "Synopsys": [r"\bsynopsys\b"], "Cadence": [r"\bcadence\b"], "Mentor": [r"\bmentor\b"],
    "Git": [r"\bgit\b"], "Jenkins": [r"\bjenkins\b"], "Docker": [r"\bdocker\b"],
}

PROTOCOLS = {
    "AXI": [r"\baxi\b", r"\baxi4\b"], "AHB": [r"\bahb\b"], "APB": [r"\bapb\b"], "AMBA": [r"\bamba\b"],
    "PCIe": [r"\bpcie\b", r"\bpci express\b"], "CXL": [r"\bcxl\b"], "USB": [r"\busb\b"],
    "DDR": [r"\bddr\b", r"\bddr[345]\b"], "LPDDR": [r"\blpddr\b"], "HBM": [r"\bhbm\b"],
    "Ethernet": [r"\bethernet\b"], "SPI": [r"\bspi\b"], "I2C": [r"\bi2c\b"], "UART": [r"\buart\b"],
    "JTAG": [r"\bjtag\b"], "NoC": [r"\bnoc\b", r"network[\s-]?on[\s-]?chip"], "SerDes": [r"\bserdes\b"],
    "RISC-V": [r"\brisc[\s-]?v\b"], "ARM": [r"\barm\b"],
}

CONCEPTS = {
    "RTL Design": [r"\brtl\b", r"register transfer level"],
    "Digital Design": [r"digital design"], "Logic Design": [r"logic design"],
    "Microarchitecture": [r"micro[\s-]?architecture"], "FSM": [r"\bfsm\b", r"state machine"],
    "Pipelining": [r"\bpipelin"], "CDC": [r"\bcdc\b", r"clock domain crossing"],
    "RDC": [r"\brdc\b", r"reset domain crossing"], "Synthesis": [r"\bsynthesis\b"],
    "STA": [r"\bsta\b", r"static timing", r"timing closure"], "Low Power": [r"low power", r"\bupf\b", r"\bcpf\b"],
    "Place and Route": [r"place and route", r"\bpnr\b", r"\bp&r\b"],
    "DFT": [r"\bdft\b", r"design for test"], "Scan": [r"\bscan\b"], "ATPG": [r"\batpg\b"],
    "MBIST": [r"\bmbist\b", r"\bbist\b"], "Lint": [r"\blint\b"],
    "FPGA Prototyping": [r"fpga prototyp", r"prototyping"], "Cache Coherence": [r"cache coherence", r"coherency"],
}

LANGUAGES = {
    "Python": [r"\bpython\b"], "C": [r"\bc\b(?!\+)"], "C++": [r"\bc\+\+\b"],
    "Tcl": [r"\btcl\b"], "Perl": [r"\bperl\b"], "Bash": [r"\bbash\b", r"shell script"],
    "Makefile": [r"\bmakefile\b", r"\bmake\b"], "MATLAB": [r"\bmatlab\b"], "Assembly": [r"\bassembly\b"],
}

# Project-area signal terms (used to match resume projects to jobs)
PROJECT_SIGNALS = {
    "FIFO": [r"\bfifo\b", r"async(hronous)? fifo"], "AXI": [r"\baxi\b"], "Cache": [r"\bcache\b"],
    "CPU": [r"\bcpu\b", r"\bprocessor\b", r"\bcore\b"], "GPU": [r"\bgpu\b"], "RISC-V": [r"\brisc[\s-]?v\b"],
    "UART": [r"\buart\b"], "SPI": [r"\bspi\b"], "I2C": [r"\bi2c\b"], "FFT": [r"\bfft\b"],
    "ALU": [r"\balu\b"], "Memory Controller": [r"memory controller", r"\bddr\b"], "SoC": [r"\bsoc\b"],
    "Convolution": [r"\bconvolution\b", r"\bcnn\b", r"accelerator"], "Router": [r"\brouter\b", r"\bnoc\b"],
}

_ALL_DICTS = {
    "hdls": HDLS, "methodologies": METHODOLOGIES, "tools": TOOLS,
    "protocols": PROTOCOLS, "concepts": CONCEPTS, "languages": LANGUAGES,
}


@dataclass
class ResumeProfileData:
    name: str = ""
    education: str = ""
    degree: str = ""
    grad_date: str = ""
    years_experience: float = 0.0
    role_focus: str = ""
    hdls: list[str] = field(default_factory=list)
    methodologies: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    protocols: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    project_signals: list[str] = field(default_factory=list)
    all_skills: list[str] = field(default_factory=list)
    raw_text_len: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text(data: bytes, filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _pdf_text(data)
    if name.endswith(".docx"):
        return _docx_text(data)
    # txt, tex, md, or unknown → decode as text
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return data.decode("latin-1", errors="ignore")


def _pdf_text(data: bytes) -> str:
    import fitz  # PyMuPDF
    text_parts = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def _docx_text(data: bytes) -> str:
    import docx
    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


# ── Parsing ──────────────────────────────────────────────────────────────────

def _match_dict(text_l: str, d: dict[str, list[str]]) -> list[str]:
    found = []
    for canonical, pats in d.items():
        if any(re.search(p, text_l) for p in pats):
            found.append(canonical)
    return found


def _extract_education(text: str) -> tuple[str, str, str]:
    t = text.lower()
    degree = ""
    if re.search(r"\bph\.?d\.?\b|doctorate", t):
        degree = "PhD"
    elif re.search(r"\b(m\.?s\.?|master)\b", t):
        degree = "MS"
    elif re.search(r"\b(b\.?s\.?|bachelor|b\.?tech|b\.?e\.?)\b", t):
        degree = "BS"
    field_m = re.search(r"\b(electrical(?:\s+and\s+computer)?\s+engineering|computer engineering|ece|eece|vlsi|microelectronics|electronics)\b", t)
    fld = field_m.group(1).upper() if field_m else ""
    grad_m = re.search(r"(?:expected|graduat\w*|class of)?\s*((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+)?(20[2-3]\d)", t)
    grad = ""
    if grad_m:
        grad = (grad_m.group(1) or "").strip().title() + " " + grad_m.group(2)
        grad = grad.strip()
    edu = " ".join(x for x in [degree, fld] if x).strip()
    return edu, degree, grad


def _extract_years(text: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:of\s+)?experience", text.lower())
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return 0.0
    return 0.0


def _extract_projects(text: str) -> list[str]:
    """Pull lines from a Projects section (best-effort)."""
    lines = text.splitlines()
    projects: list[str] = []
    in_section = False
    for ln in lines:
        s = ln.strip()
        low = s.lower()
        if re.match(r"^(academic |technical |key |relevant )?projects?\b[:\s]*$", low) or low in ("projects", "project experience"):
            in_section = True
            continue
        if in_section:
            # stop at next major section header
            if re.match(r"^(experience|work experience|education|skills|certifications|publications|awards|employment)\b", low):
                break
            if len(s) >= 6 and not s.isupper():
                # title-ish line (often "Project Name — desc" or a bullet)
                clean = re.sub(r"^[•\-\*•●▪]+\s*", "", s)
                if clean and len(clean) <= 160:
                    projects.append(clean)
            if len(projects) >= 12:
                break
    return projects[:12]


def _infer_role_focus(profile: ResumeProfileData) -> str:
    dv = len([x for x in profile.methodologies if x in ("UVM", "SVA", "Functional Coverage", "Constrained Random", "Scoreboard", "Testbench", "Regression")])
    rtl = len([x for x in profile.concepts if x in ("RTL Design", "Digital Design", "Logic Design", "Microarchitecture", "FSM", "Pipelining", "Synthesis")])
    dft = len([x for x in profile.concepts if x in ("DFT", "Scan", "ATPG", "MBIST")])
    fpga = 1 if ("FPGA Prototyping" in profile.concepts or "Vivado" in profile.tools or "Quartus" in profile.tools) else 0
    formal = 1 if "Formal Verification" in profile.methodologies else 0
    scores = {"Design Verification": dv, "RTL Design": rtl, "DFT": dft, "FPGA": fpga, "Formal Verification": formal}
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "VLSI (general)"


def parse_resume(data: bytes, filename: str) -> ResumeProfileData:
    text = extract_text(data, filename)
    t = text.lower()
    p = ResumeProfileData(raw_text_len=len(text))

    p.hdls = _match_dict(t, HDLS)
    p.methodologies = _match_dict(t, METHODOLOGIES)
    p.tools = _match_dict(t, TOOLS)
    p.protocols = _match_dict(t, PROTOCOLS)
    p.concepts = _match_dict(t, CONCEPTS)
    p.languages = _match_dict(t, LANGUAGES)
    p.project_signals = _match_dict(t, PROJECT_SIGNALS)
    p.projects = _extract_projects(text)
    p.education, p.degree, p.grad_date = _extract_education(text)
    p.years_experience = _extract_years(text)

    # name = first non-empty line that looks like a name (heuristic)
    for ln in text.splitlines():
        s = ln.strip()
        if 3 <= len(s) <= 40 and re.match(r"^[A-Za-z.\s'-]+$", s) and len(s.split()) <= 4:
            p.name = s
            break

    p.all_skills = sorted(set(
        p.hdls + p.methodologies + p.tools + p.protocols + p.concepts + p.languages
    ))
    p.role_focus = _infer_role_focus(p)
    return p
