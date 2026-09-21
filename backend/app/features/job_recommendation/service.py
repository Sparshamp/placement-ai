"""Job recommendation service — preprocess resume, hybrid match, tailor resume."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.features.job_recommendation import session_store, skill_gap_analysis
from app.features.job_recommendation.config import (
    ALLOWED_RESUME_EXTENSIONS,
    COLBERT_TOP_N,
    DEFAULT_TOP_K,
    MAX_RESUME_BYTES,
    SKILL_GAP_MODEL,
    STAGE1_N_RESULTS,
)
from app.features.job_recommendation.ingest_jobs import ensure_jobs_index
from app.features.job_recommendation.resume_processing.pipeline import process_one
from app.features.job_recommendation.resume_processing.step1_parser import parse_resume_bytes
from app.features.job_recommendation.skill_gap_llm import explain_with_llm
from app.features.job_recommendation.skill_overlap import enrich_recommendations

logger = logging.getLogger(__name__)

_engine = None
_engine_error: str | None = None
_engine_lock = threading.Lock()


def _public_error(status: int, message: str, technical: str | None = None) -> HTTPException:
    if technical:
        logger.exception("%s", technical) if status >= 500 else logger.warning("%s", technical)
    else:
        logger.warning("%s", message)
    return HTTPException(status_code=status, detail=message)


def get_engine():
    global _engine, _engine_error
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        if _engine_error:
            raise _public_error(
                503,
                "Job recommendations are temporarily unavailable. Please try again later.",
                _engine_error,
            )
        try:
            count = ensure_jobs_index()
            if count == 0:
                raise RuntimeError("The jobs index is empty after ingest.")
            from app.features.job_recommendation.models.hybrid_pipeline_matcher import (
                HybridPipelineEngine,
            )

            _engine = HybridPipelineEngine()
            return _engine
        except HTTPException:
            raise
        except Exception as exc:
            _engine_error = str(exc)
            logger.exception("Failed to initialize job recommendation engine")
            raise _public_error(
                503,
                "Job recommendations are not ready yet. The matching models or job index could not be loaded.",
                str(exc),
            )


def _safe_filename(name: str) -> str:
    return Path(name or "resume").name


def _split_skill_string(text: str) -> list[str]:
    if not text or text in ("Not Listed", "None"):
        return []
    parts = [p.strip(" -:.") for p in str(text).replace(";", ",").split(",")]
    return [p for p in parts if p]


def _summarize(text: str, limit: int = 280) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _to_card(rec: dict) -> dict:
    skills = rec.get("job_skills") or _split_skill_string(rec.get("skills", ""))
    matching = rec.get("matching_skills") or []
    score = rec.get("score")
    relevance = None
    if isinstance(score, (int, float)):
        relevance = max(0, min(99, int(round(float(score) * 100))))
    return {
        "jobIndex": int(rec.get("job_index", -1)),
        "rank": int(rec.get("rank", 0)),
        "title": rec.get("title") or "Untitled role",
        "company": rec.get("company") or "",
        "location": rec.get("location") or "",
        "workType": rec.get("work_type") or "",
        "domain": rec.get("domain") or "",
        "experienceLevel": rec.get("experience_level") or "",
        "salary": rec.get("salary") or "",
        "skills": skills[:10],
        "matchingSkills": matching[:8],
        "summary": _summarize(rec.get("description") or ""),
        "relevancePercent": relevance,
    }


def _to_detail(rec: dict) -> dict:
    card = _to_card(rec)
    card["description"] = rec.get("description") or ""
    card["relevanceNote"] = rec.get("relevance_note") or ""
    card["relatedSkills"] = rec.get("related_skills") or []
    return card


def _profile_from_preprocessed(preprocessed: dict) -> dict:
    entities = preprocessed.get("entities") or {}
    return {
        "name": entities.get("name") or "",
        "email": entities.get("email") or "",
        "location": entities.get("location") or "",
        "years_exp": entities.get("years_exp") or "",
        "skills": (entities.get("skills") or [])[:16],
    }


async def recommend_from_resume(resume: UploadFile, top_k: int = DEFAULT_TOP_K) -> dict:
    filename = _safe_filename(resume.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_RESUME_EXTENSIONS:
        raise _public_error(400, "Please upload a PDF, Word (.docx), or text resume.")

    raw = await resume.read()
    if not raw:
        raise _public_error(400, "The uploaded file is empty.")
    if len(raw) > MAX_RESUME_BYTES:
        raise _public_error(400, "That file is too large. Please upload a resume under 5 MB.")

    try:
        parsed = parse_resume_bytes(raw, filename)
    except ValueError as exc:
        raise _public_error(400, str(exc))
    except Exception as exc:
        raise _public_error(400, "We couldn't read this resume. Try a text-based PDF or DOCX.", str(exc))

    try:
        preprocessed = process_one(parsed)
    except RuntimeError as exc:
        raise _public_error(503, str(exc), str(exc))
    except Exception as exc:
        raise _public_error(
            500,
            "We couldn't analyze this resume. Please try another file.",
            str(exc),
        )

    embeddings = preprocessed.get("embeddings") or {}
    if not embeddings.get("query_vector"):
        raise _public_error(400, "We couldn't find enough information in this resume to recommend jobs.")

    engine = get_engine()
    try:
        recs = engine.recommend(
            preprocessed,
            top_k=top_k,
            stage1_n_results=STAGE1_N_RESULTS,
            colbert_top_n=COLBERT_TOP_N,
        )
    except Exception as exc:
        raise _public_error(
            500,
            "We couldn't generate job recommendations right now. Please try again.",
            str(exc),
        )

    if not recs:
        raise _public_error(
            404,
            "No matching jobs were found for this resume. Try a more detailed resume, or make sure the job index has been built.",
        )

    enriched = enrich_recommendations(preprocessed, recs)
    session_id = session_store.create_session({
        "preprocessed": preprocessed,
        "recommendations": enriched,
        "profile": _profile_from_preprocessed(preprocessed),
    })
    return {
        "sessionId": session_id,
        "profile": _profile_from_preprocessed(preprocessed),
        "jobs": [_to_card(rec) for rec in enriched],
    }


def get_session_jobs(session_id: str) -> dict:
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise _public_error(404, "This recommendation session was not found. Please upload your resume again.")
    return {
        "sessionId": session_id,
        "profile": session["profile"],
        "jobs": [_to_card(rec) for rec in session["recommendations"]],
    }


def get_job_detail(session_id: str, job_index: int) -> dict:
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise _public_error(404, "This recommendation session was not found. Please upload your resume again.")
    for rec in session["recommendations"]:
        if int(rec.get("job_index", -1)) == int(job_index):
            return _to_detail(rec)
    raise _public_error(404, "That job is not in your current recommendations.")


def generate_tailored(session_id: str, job_index: int) -> dict:
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise _public_error(404, "This recommendation session was not found. Please upload your resume again.")

    rec = next((r for r in session["recommendations"] if int(r.get("job_index", -1)) == int(job_index)), None)
    if rec is None:
        raise _public_error(404, "That job is not in your current recommendations.")

    try:
        from app.features.job_recommendation.tailoring.resume_tailoring import generate_tailored_resume

        artifact = generate_tailored_resume(session["preprocessed"], rec)
    except Exception as exc:
        raise _public_error(
            500,
            "We couldn't tailor your resume for this job. Please try again.",
            str(exc),
        )

    return {
        "jobIndex": int(job_index),
        "title": rec.get("title") or "",
        "company": rec.get("company") or "",
        "resumeMarkdown": artifact.get("resume_markdown") or "",
        "summary": artifact.get("tailoring_summary") or (
            "This version reorganizes your original resume for this role. No new qualifications were added."
        ),
        "focus": artifact.get("ats_focus") or rec.get("matching_skills") or [],
        "tailoredFromOriginal": True,
        "downloadPath": f"/api/job-recommendation/sessions/{session_id}/jobs/{job_index}/tailored-resume.docx",
        "_docx_path": artifact.get("docx_path") or "",
    }


def tailored_docx_path(session_id: str, job_index: int) -> Path:
    payload = generate_tailored(session_id, job_index)
    path = Path(payload.get("_docx_path") or "")
    if not path.exists():
        raise _public_error(500, "The tailored resume file could not be created.")
    return path

def _to_skill_gap_job(job: dict) -> dict:
    return {
        "jobIndex": int(job.get("job_index") or -1),
        "title": job.get("title") or "",
        "company": job.get("company") or "",
        "matchingSkills": job.get("matching_skills") or [],
        "missingSkills": job.get("missing_skills") or [],
        "matchRatio": job.get("match_ratio") or 0.0,
    }


def _to_skill_gap_response(session_id: str, grounded: dict, explanation: dict) -> dict:
    focus = grounded.get("focus_track")
    return {
        "sessionId": session_id,
        "resumeSkills": grounded.get("resume_skills") or [],
        "jobsAnalyzed": grounded.get("jobs_analyzed") or 0,
        "jobBreakdown": [_to_skill_gap_job(j) for j in grounded.get("job_breakdown") or []],
        "repeatedGaps": [
            {"skill": g["skill"], "blocksRoles": g["blocks_roles"], "roles": g["roles"]}
            for g in grounded.get("repeated_gaps") or []
        ],
        "learningPath": [
            {
                "skill": s["skill"],
                "category": s["category"],
                "blocksRoles": s["blocks_roles"],
                "prerequisiteSkills": s["prerequisite_skills"],
                "readiness": s["readiness"],
                "note": s["note"],
            }
            for s in grounded.get("learning_path") or []
        ],
        "focusTrack": (
            {"category": focus["category"], "score": focus["score"], "reason": focus["reason"]}
            if focus else None
        ),
        "closestRoles": [_to_skill_gap_job(j) for j in grounded.get("closest_roles") or []],
        "skillGraph": grounded.get("skill_graph") or {"nodes": [], "edges": []},
        "explanation": {
            "summary": explanation.get("summary") or "",
            "jobAdvice": explanation.get("job_advice") or [],
            "strategicLearningSequence": explanation.get("strategic_learning_sequence") or [],
            "usedLlm": bool(explanation.get("used_llm")),
            "backend": explanation.get("backend") or "grounded-fallback",
        },
    }


def analyze_session_recommendations(session_id: str, top_n: int = 5) -> dict:
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise _public_error(404, "This recommendation session was not found. Please upload your resume again.")

    grounded = skill_gap_analysis.analyze_recommendations(
        session["preprocessed"], session["recommendations"], top_n_jobs=top_n,
    )
    explanation = explain_with_llm(grounded, model=SKILL_GAP_MODEL)
    return _to_skill_gap_response(session_id, grounded, explanation)