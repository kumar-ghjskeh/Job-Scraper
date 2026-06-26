"""Résumé Studio — per-job résumé tailoring.

Two paths, both driven by the same assembled prompt:
  1. Hand-off: the frontend copies the prompt into the user's Claude/ChatGPT Pro.
  2. In-app: generate_with_gemini() calls Google's free Gemini API server-side.

The prompt assembly is pure and deterministic — it's built from the exact job
record + the user's master LaTeX, so the output is always bound to the job in view.
"""

from __future__ import annotations

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def build_tailor_prompt(
    *,
    job_title: str,
    company: str,
    description: str,
    master_latex: str,
    missing_keywords: list[str],
    instructions: str = "",
) -> str:
    """Assemble the elite-grade tailoring prompt. Deterministic — no AI here."""
    kw = ", ".join(k for k in missing_keywords if k) or "(none detected — rely on the job description)"
    extra = f"\n\nADDITIONAL INSTRUCTIONS FROM THE CANDIDATE:\n{instructions.strip()}" if instructions.strip() else ""
    master = master_latex.strip() or "(no master résumé provided — ask the candidate to paste their LaTeX)"
    desc = (description or "").strip() or "(no description captured for this role)"

    return f"""You are a world-class technical résumé writer and ATS-optimization expert for semiconductor RTL design and design-verification roles. Rewrite the candidate's LaTeX résumé so it is maximally tailored to the target job below and scores as highly as possible on ATS keyword-matching tools (Jobscan, Workday, Greenhouse, Lever) — while remaining 100% truthful.

TARGET ROLE: {job_title} at {company}

JOB DESCRIPTION:
{desc}

PRIORITY KEYWORDS & SKILLS TO INTEGRATE (terms this job emphasizes that the résumé is missing or under-using — weave in EVERY one the candidate can truthfully claim, using the job's exact wording):
{kw}

CANDIDATE'S MASTER RÉSUMÉ (LaTeX — the exact template, packages, and structure to preserve):
{master}

REWRITE OBJECTIVES (in priority order):
1. ATS keyword coverage — mirror the job description's exact terminology. Use the priority keywords above verbatim wherever the candidate has the experience. Spell out each acronym once with the acronym in parentheses, e.g. "Universal Verification Methodology (UVM)", so both the long form and acronym match.
2. Tailored summary — rewrite the top summary to target THIS role and company, leading with the candidate's most relevant strengths for it.
3. Reordered emphasis — surface the most relevant projects, experience, and skills first; de-emphasize or trim unrelated content if the page would overflow.
4. Strong bullets — keep bullets action-verb-led and quantified (preserve the candidate's real numbers); rephrase to echo the job's language and responsibilities.

HARD RULES:
- Preserve the master résumé's LaTeX documentclass, packages, section order, and formatting EXACTLY. Edit only the text content. The output must compile unchanged in Overleaf.
- NEVER invent or imply employers, titles, dates, degrees, certifications, tools, or skills the candidate does not already show. Truthfulness outranks keyword-matching — if a priority keyword cannot be supported truthfully, omit it.
- Keep it to the same length / number of pages as the master.
- Output ONLY the complete, compilable LaTeX document, from \\documentclass to \\end{{document}} — no commentary, no explanations, no markdown code fences.{extra}"""


def gemini_enabled() -> bool:
    return bool(settings.gemini_api_key)


def generate_with_gemini(prompt: str) -> str:
    """Call Google's free Gemini API and return the generated LaTeX. Raises
    RuntimeError with a readable message on any failure so the API can surface it."""
    if not settings.gemini_api_key:
        raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY to enable in-app generation.")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    gen_config: dict = {"temperature": 0.3, "maxOutputTokens": 8192}
    # Gemini 2.5 models spend output tokens on internal "thinking", which can
    # truncate the résumé. Disable it so the full budget produces the document.
    if "2.5" in settings.gemini_model:
        gen_config["thinkingConfig"] = {"thinkingBudget": 0}
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                url,
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": gen_config,
                },
            )
    except Exception as e:
        raise RuntimeError(f"Could not reach Gemini: {e}") from e

    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except Exception:
            detail = resp.text[:200]
        raise RuntimeError(f"Gemini error ({resp.status_code}): {detail or 'request failed'}")

    try:
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        raise RuntimeError(f"Unexpected Gemini response: {e}") from e

    # Strip accidental markdown fences if the model wraps the LaTeX.
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
