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

    return f"""You are an expert technical résumé writer specializing in semiconductor RTL design and design-verification roles. Tailor the candidate's LaTeX résumé to the target job below — truthfully, never fabricating anything.

TARGET ROLE: {job_title} at {company}

JOB DESCRIPTION:
{desc}

KEYWORDS / SKILLS THIS RÉSUMÉ SHOULD SURFACE (only where the candidate genuinely has the experience — never invent):
{kw}

CANDIDATE'S MASTER RÉSUMÉ (LaTeX — preserve this exact documentclass, packages, section order, and styling):
{master}

RULES:
- Keep the master résumé's LaTeX template, packages, section order, and formatting EXACTLY. Edit content only.
- Rephrase the summary and bullet points to mirror this job's language and foreground the relevant experience and keywords the candidate already has.
- Do NOT invent employers, titles, dates, degrees, certifications, or skills the candidate does not show. Truthfulness always wins over keyword-matching.
- Prioritize the most relevant experience for THIS role; de-emphasize or trim unrelated content if space requires.
- Output ONLY the complete, compilable LaTeX document. No commentary, no explanations, no markdown code fences.{extra}"""


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
    try:
        with httpx.Client(timeout=90) as client:
            resp = client.post(
                url,
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096},
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
