"""Optional LLM explanation layer for skill-gap analysis.

Never replaces the grounded analysis — it only rewrites it into a
human-friendly summary, job-specific advice, and a strategic learning
sequence. Falls back to a grounded, template-based explanation if
Ollama is unavailable.
"""
from __future__ import annotations

import json
import logging
from typing import Dict

from app.features.job_recommendation.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)

EXPLANATION_PROMPT = """
You are a career coach helping a candidate understand their skill gaps
against a set of recommended jobs.

You are given a grounded, already-computed analysis: current skills,
per-job matching/missing skills, a prerequisite-based learning path,
the closest-matching roles, and repeated skill gaps.

Do not invent skills, roles, or numbers that are not present in the
input. Only rewrite and explain what is already there.

Output requirements:
- Return ONLY valid JSON.
- `summary`: 2-4 sentences, human-friendly, naming the biggest opportunity.
- `job_advice`: one entry per job in the input, each with `title` and
  `advice` (1-2 sentences, specific to that job's missing skills).
- `strategic_learning_sequence`: the input's learning-path skills,
  reordered if useful, as a flat list of skill names.
""".strip()

_RESPONSE_EXAMPLE = {
    "summary": (
        "Your strongest opportunity is ML / AI — closing PyTorch and MLOps alone "
        "would unlock 2 of your top 5 recommended roles."
    ),
    "job_advice": [
        {
            "title": "Machine Learning Engineer",
            "advice": "You're missing PyTorch, MLOps, NumPy, and Azure — start with PyTorch since you already know Python and Machine Learning.",
        },
        {
            "title": "Data Scientist",
            "advice": "Your resume already covers Python, Machine Learning, Scikit-learn, and Pandas; Scala and NumPy are the main gaps.",
        },
    ],
    "strategic_learning_sequence": ["PyTorch", "MLOps", "NumPy", "SQL"],
}


def _build_llm_payload(grounded: dict) -> dict:
    return {
        "current_skills": grounded.get("resume_skills", [])[:30],
        "jobs": [
            {
                "title": j["title"],
                "company": j["company"],
                "matching_skills": j["matching_skills"],
                "missing_skills": j["missing_skills"],
            }
            for j in grounded.get("job_breakdown", [])
        ],
        "learning_path": [
            {
                "skill": s["skill"],
                "category": s["category"],
                "blocks_roles": s["blocks_roles"],
                "readiness": s["readiness"],
            }
            for s in grounded.get("learning_path", [])
        ],
        "closest_roles": [
            {"title": j["title"], "company": j["company"], "match_ratio": j["match_ratio"]}
            for j in grounded.get("closest_roles", [])
        ],
        "repeated_gaps": grounded.get("repeated_gaps", []),
        "focus_track": grounded.get("focus_track"),
    }


def _fallback_explanation(grounded: dict) -> Dict:
    summary_bits = []
    focus = grounded.get("focus_track")
    if focus:
        summary_bits.append(f"Your biggest opportunity is {focus['category']} — {focus['reason']}")
    gaps = grounded.get("repeated_gaps") or []
    if gaps:
        top = gaps[0]
        summary_bits.append(
            f"{top['skill']} alone is blocking {top['blocks_roles']} of your top recommended roles."
        )
    job_advice = [
        {
            "title": j["title"],
            "advice": (
                f"You're missing {', '.join(j['missing_skills'])}."
                if j["missing_skills"]
                else "Your resume already covers this role's core skills."
            ),
        }
        for j in grounded.get("job_breakdown", [])
    ]
    sequence = [step["skill"] for step in grounded.get("learning_path", [])]
    return {
        "summary": " ".join(summary_bits) or "No major skill gaps were found across your top recommendations.",
        "job_advice": job_advice,
        "strategic_learning_sequence": sequence,
        "used_llm": False,
        "backend": "grounded-fallback",
    }


def _call_ollama_json(prompt: str, model: str = OLLAMA_MODEL) -> Dict:
    import requests

    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": model or OLLAMA_MODEL,
        "stream": False,
        "options": {"temperature": 0.3},
        "messages": [
            {"role": "system", "content": "Return only valid JSON. Never invent skills or numbers."},
            {"role": "user", "content": prompt},
        ],
    }
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    text = (resp.json().get("message", {}).get("content", "") or "").strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[: -3].strip()

    start = text.find("{")
    if start == -1:
        raise RuntimeError("Ollama did not return any JSON object.")

    # Parse only the first complete JSON value and ignore anything the model
    # appended after it (stray text, a repeated object, trailing newlines).
    decoder = json.JSONDecoder()
    data, _ = decoder.raw_decode(text[start:])
    if not isinstance(data, dict):
        raise RuntimeError("Ollama did not return a JSON object.")
    data["_llm_backend"] = "ollama"
    data["_llm_model"] = model or OLLAMA_MODEL
    return data


def explain_with_llm(grounded: dict, model: str = OLLAMA_MODEL) -> Dict:
    payload = _build_llm_payload(grounded)
    prompt = (
        f"{EXPLANATION_PROMPT}\n\nInput JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Return ONLY a JSON object with the SAME KEYS and shapes as this example "
        "(write your own text based on the input above — do not copy the example's "
        "wording or numbers):\n"
        f"{json.dumps(_RESPONSE_EXAMPLE, indent=2)}"
    )
    try:
        result = _call_ollama_json(prompt, model)
        summary = result.get("summary") or ""
        job_advice = result.get("job_advice") or []
        sequence = result.get("strategic_learning_sequence") or []
        if not summary and not job_advice and not sequence:
            raise RuntimeError(f"Ollama returned JSON with no usable fields: {result!r}")
        return {
            "summary": summary,
            "job_advice": job_advice,
            "strategic_learning_sequence": sequence,
            "used_llm": True,
            "backend": result.get("_llm_backend") or "ollama",
        }
    except Exception as exc:
        logger.warning("Ollama explanation unavailable (%s); using grounded fallback", exc)
        return _fallback_explanation(grounded)