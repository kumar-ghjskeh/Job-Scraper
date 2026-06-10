"""Tests for role flag classification and software exclusion."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from backend.app.scoring import (
    classify_role_flags,
    is_software_only,
    is_hardware_software_codesign,
)


# ── is_software_only ──────────────────────────────────────────────────────────

def test_ml_compiler_is_software_only():
    assert is_software_only("ML Compiler Engineer", "Python LLVM compiler optimization") is True


def test_sde_is_software_only():
    assert is_software_only("Software Development Engineer", "AWS cloud backend services") is True


def test_backend_engineer_is_software_only():
    assert is_software_only("Backend Engineer", "REST APIs microservices Kubernetes") is True


def test_dv_engineer_not_software_only():
    assert is_software_only("Design Verification Engineer", "UVM SystemVerilog testbench") is False


def test_rtl_engineer_not_software_only():
    assert is_software_only("RTL Design Engineer", "ASIC digital design Verilog") is False


def test_hw_sw_codesign_not_pure_software():
    # Has HW overlap signals — should not be flagged as pure software
    assert is_software_only(
        "C/C++ HW/SW Co-Design Engineer",
        "RTL co-simulation hardware accelerator FPGA"
    ) is False


def test_software_with_hw_overlap_not_excluded():
    # "firmware" has HW overlap
    assert is_software_only("Firmware Engineer", "embedded C ARM Cortex FPGA") is False


def test_full_stack_is_software_only():
    assert is_software_only("Full Stack Engineer", "React Node.js PostgreSQL Docker") is True


def test_devops_is_software_only():
    assert is_software_only("DevOps Engineer", "CI/CD Kubernetes Terraform AWS") is True


# ── is_hardware_software_codesign ─────────────────────────────────────────────

def test_hw_sw_codesign_detected():
    assert is_hardware_software_codesign(
        "Hardware/Software Co-Design Engineer",
        "RTL simulation C++ driver development hardware verification"
    ) is True


def test_pure_dv_not_codesign():
    assert is_hardware_software_codesign(
        "Design Verification Engineer",
        "UVM SystemVerilog testbench constrained random"
    ) is False


# ── classify_role_flags ───────────────────────────────────────────────────────

def test_dv_engineer_flags():
    flags = classify_role_flags("Design Verification Engineer", "UVM SystemVerilog testbench")
    assert flags["is_design_verification"] is True
    assert flags["is_software_only"] is False
    # DV and RTL flags are allowed to co-exist — DV engineers work with RTL


def test_rtl_engineer_flags():
    flags = classify_role_flags("RTL Design Engineer", "Verilog digital design logic synthesis")
    assert flags["is_rtl_design"] is True
    assert flags["is_software_only"] is False


def test_fpga_engineer_flags():
    flags = classify_role_flags("FPGA Design Engineer", "VHDL Xilinx Vivado FPGA implementation")
    assert flags["is_fpga"] is True


def test_formal_verification_flags():
    flags = classify_role_flags("Formal Verification Engineer", "JasperGold SVA property checking")
    assert flags["is_formal"] is True


def test_emulation_engineer_flags():
    flags = classify_role_flags("Emulation Engineer", "Palladium ZeBu FPGA-based emulation")
    assert flags["is_emulation"] is True


def test_dft_engineer_flags():
    flags = classify_role_flags("DFT Engineer", "ATPG scan insertion BIST JTAG")
    assert flags["is_dft"] is True


def test_software_only_flags():
    flags = classify_role_flags("Software Development Engineer", "Python AWS backend REST API")
    assert flags["is_software_only"] is True
    assert flags["is_design_verification"] is False
    assert flags["is_rtl_design"] is False


def test_flags_all_keys_present():
    flags = classify_role_flags("Design Verification Engineer", "UVM")
    expected_keys = {
        "is_design_verification", "is_rtl_design", "is_soc_verification",
        "is_cpu_gpu_verification", "is_fpga", "is_formal", "is_emulation",
        "is_pre_silicon", "is_post_silicon", "is_validation", "is_dft",
        "is_eda_tools", "is_software_only", "is_hardware_software_codesign",
    }
    assert expected_keys == set(flags.keys())


# ── DV expansion — the "too few results" regression ───────────────────────────

def test_dv_subsystem_verification_classified():
    flags = classify_role_flags("Subsystem Verification Engineer", "SoC verification UVM")
    assert flags["is_design_verification"] or flags["is_soc_verification"]


def test_dv_ip_verification_classified():
    flags = classify_role_flags("IP Verification Engineer", "block-level UVM testbench")
    assert flags["is_design_verification"] is True


def test_soc_verification_engineer_flags():
    flags = classify_role_flags("SoC Verification Engineer", "full-chip UVM coverage-driven")
    assert flags["is_soc_verification"] is True
