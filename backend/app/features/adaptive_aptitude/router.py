"""
api/main.py
-----------
FastAPI backend exposing the adaptive platform endpoints.

Endpoints:
  POST /session/start              — Start a practice session (scoped by practice_category)
  GET  /question/next              — Get next question for student in a session
  POST /question/answer            — Submit an answer, get updated mastery + next question
  GET  /student/{id}/summary       — Full mastery dashboard
  GET  /student/{id}/history       — Recent interaction log
  GET  /student/{id}/skills        — Per-concept skill scores for one canonical_subject
  GET  /practice-categories        — The 5 session-scoping buckets
  GET  /subjects                   — The 22 canonical subjects (dashboard/reporting only)

PERSISTENCE (Phase 2 fix, part 3 -- the last of the three from the original
review): mastery/session/response state now lives in Postgres
(student_sessions / student_responses / student_mastery, per
db/schema_extended.sql), via core.knowledge_model_pg.
PostgresStudentKnowledgeModel, not SQLite (adaptive_platform.db). This is
a drop-in replacement for the old StudentKnowledgeModel -- same method
names/shapes -- except for two real, deliberate differences:
  1. session_id is now a REAL Postgres UUID returned by start_session(),
     not a disconnected uuid4() generated client-side and never actually
     linked to the logged row (the old SQLite version's bug).
  2. Submitting an answer now requires that session_id back
     (AnswerRequest.session_id) -- student_responses.session_id is a real
     NOT NULL foreign key, unlike SQLite's interaction_log, which never
     linked a response to a session at all.
adaptive_platform.db / SQLite is no longer used anywhere in this file.

SESSION SCOPING: sessions are scoped by practice_category (5 broad
buckets), not canonical_subject (22 finer subjects) -- see
core/question_selector.py module docstring for the full rationale.

DATA SOURCE: loads the real ~2,539-concept Postgres DAG + questions_resolved
via experiments.data, not build_default_dag() / the raw questions table.
"""

from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.features.adaptive_aptitude.core.knowledge_model_pg import PostgresStudentKnowledgeModel
from app.features.adaptive_aptitude.core.question_selector import QuestionSelector
from app.features.adaptive_aptitude.data_resolved import load_concept_dag, load_questions_resolved

router = APIRouter(prefix="/api/adaptive-aptitude", tags=["adaptive-aptitude"])

# ── Load resources at startup ──────────────────────────────────────────────

KM = PostgresStudentKnowledgeModel()

QUESTIONS_DF = None
DAG = None

try:
    QUESTIONS_DF = load_questions_resolved()   # full bank, all practice_categories/subjects
    DAG = load_concept_dag()                   # real ~2,539-concept Postgres DAG
except Exception as e:
    print(f"Could not load questions/DAG from Postgres ({e}); starting empty. "
          f"Run `docker compose up -d` and the ingestion scripts first.")
    QUESTIONS_DF = pd.DataFrame(columns=[
        "question_id", "canonical_subject", "canonical_topic", "subtopic",
        "concept_id", "practice_category", "question", "option_a", "option_b",
        "option_c", "option_d", "correct_answer", "difficulty",
        "time_expected_minutes", "image_url",
    ])
    from app.features.adaptive_aptitude.core.concept_dag import ConceptDAG
    DAG = ConceptDAG()  # empty, not build_default_dag() -- fails loudly and
                         # obviously instead of silently serving the wrong graph


def get_selector() -> QuestionSelector:
    return QuestionSelector(QUESTIONS_DF, DAG, KM, epsilon=0.20)


def get_question_lookup(question_id: str):
    """Server-side lookup of the ground-truth answer + question type by
    question_id. NEVER trust a client-supplied correct_answer -- see
    submit_answer. Returns None if the question_id doesn't exist."""
    row = QUESTIONS_DF[QUESTIONS_DF["question_id"].astype(str) == str(question_id)]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "correct_answer": r["correct_answer"],
        "question_type": r.get("canonical_question_type") or r.get("question_type") or "mcq",
    }


def _split_multi(raw: str) -> set:
    """'A;C' -> {'A', 'C'}. Trims whitespace, upper-cases, drops empties
    so 'A; C' / 'a;c' / a trailing ';' all normalize the same way."""
    return {part.strip().upper() for part in str(raw or "").split(";") if part.strip()}


def grade_answer(question_type: str, selected_answer: str, true_answer: str):
    """Returns (is_correct: bool, detail: dict | None).

    multi_select needs a SET comparison, not exact-string equality --
    "A;C" and "C;A" are the same answer, and a student picking a
    strict subset/superset of the correct options is a different,
    reportable outcome (partial credit for feedback purposes) from
    picking none of them at all, even though only an EXACT match to
    the full correct set counts as `is_correct` for BKT/mastery
    purposes (multi-select MCQs don't have partial-credit scoring in
    the source exams either -- GATE etc. mark them fully right or
    fully wrong).

    Every other type keeps the original case-insensitive exact-string
    comparison (a single letter for mcq/image_based/match_following, or
    raw text for numerical/fill_blank).
    """
    if question_type == "multi_select":
        correct_set = _split_multi(true_answer)
        selected_set = _split_multi(selected_answer)
        is_correct = bool(correct_set) and selected_set == correct_set
        if is_correct:
            status = "correct"
        elif selected_set & correct_set:
            status = "partial"
        else:
            status = "incorrect"
        detail = {
            "type": "multi_select",
            "status": status,
            "correct_options": sorted(correct_set),
            "selected_options": sorted(selected_set),
            "missed_options": sorted(correct_set - selected_set),
            "extra_options": sorted(selected_set - correct_set),
        }
        return is_correct, detail

    is_correct = str(selected_answer).strip().upper() == str(true_answer).strip().upper()
    return is_correct, None


# ── Request / Response models ──────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    student_id: str
    practice_category: str           # one of the 5 session-scoping buckets, e.g. "Core CS (Systems & Theory)"
    num_questions: int = 10

class AnswerRequest(BaseModel):
    student_id: str
    session_id: str                  # from /session/start's response -- required, see module docstring
    practice_category: str           # which session this answer belongs to -- needed so the
                                      # "next question" pick stays in the same category pool
    question_id: str
    concept_id: str
    subject: str                     # this SPECIFIC question's canonical_subject (e.g. "Databases") --
                                      # NOT the same as practice_category; needed for BKT param lookup
                                      # and dashboard mastery rollups
    topic: str                       # canonical_topic
    subtopic: str
    difficulty: str
    selected_answer: str             # "A", "B", "C", or "D" -- for multi_select
                                      # questions, every selected letter joined
                                      # with ";" e.g. "A;C" (any order; the
                                      # backend compares as a set, not a string)
    time_taken_sec: float = 0.0
    # NOTE: correct_answer is intentionally NOT accepted here. It was
    # previously client-supplied and trusted as-is -- a student's frontend
    # could set correct_answer = selected_answer and always score 100%.
    # The server looks it up itself via get_question_lookup(), keyed by
    # question_id, and the client has no way to influence that.


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/")
def root():
    return {"status": "running", "service": "Adaptive Test Prep Platform"}


@router.get("/practice-categories")
def list_practice_categories():
    """The 5 session-scoping buckets -- what a student picks to start a session."""
    categories = QUESTIONS_DF["practice_category"].dropna().unique().tolist() if QUESTIONS_DF is not None else []
    return {"practice_categories": categories}


@router.get("/subjects")
def list_subjects():
    """The 22 canonical subjects -- for dashboard/reporting (e.g.
    /student/{id}/skills), NOT for starting a session. Use
    /practice-categories for that."""
    subjects = QUESTIONS_DF["canonical_subject"].dropna().unique().tolist() if QUESTIONS_DF is not None else []
    return {"subjects": subjects}


@router.post("/session/start")
def start_session(req: SessionStartRequest):
    """
    Start a practice session scoped to one practice_category. Returns the
    REAL session_id (a Postgres UUID from student_sessions) and the first
    batch of questions selected by the adaptive engine, drawn from every
    canonical_subject inside that category.

    The client must hold onto session_id and send it back with every
    /question/answer call for this session (AnswerRequest.session_id).
    """
    selector = get_selector()
    questions = selector.select_session_questions(req.student_id, req.practice_category, req.num_questions)

    if not questions:
        raise HTTPException(404, f"No questions found for practice_category: {req.practice_category}")

    session_id = KM.start_session(req.student_id, req.practice_category)

    # Same stripping as /question/next and the next_question field in
    # /question/answer -- the client should never receive correct_answer
    # before the question is actually submitted. This was previously
    # missed here: the initial batch was returned raw, straight from
    # select_session_questions(), leaking every answer key up front.
    safe_questions = [
        {k: (v if v == v else None) for k, v in q.items() if k != "correct_answer"}
        for q in questions
    ]

    return {
        "session_id":        session_id,
        "student_id":        req.student_id,
        "practice_category": req.practice_category,
        "questions":         safe_questions,
        "count":             len(safe_questions)
    }


@router.get("/question/next")
def get_next_question(student_id: str, practice_category: str):
    """
    Get the single next best question for a student within a
    practice_category session. Called after each answered question during
    a live session.
    """
    selector = get_selector()
    question = selector.select_question(student_id, practice_category)

    if question is None:
        raise HTTPException(404, "No suitable question found")

    # Strip the answer key and clean NaN values for JSON serialization --
    # the client should never receive correct_answer up front.
    return {k: (v if v == v else None) for k, v in question.items() if k != "correct_answer"}


@router.post("/question/answer")
def submit_answer(req: AnswerRequest):
    """
    Submit a student's answer. Updates BKT/EMA mastery, logs the response
    against req.session_id, and returns:
    - Whether the answer was correct
    - Updated skill scores for this concept
    - Next recommended question (same practice_category session)

    correct_answer is looked up server-side by question_id -- never taken
    from the request (see AnswerRequest / get_question_lookup docstrings).
    """
    lookup = get_question_lookup(req.question_id)
    if lookup is None:
        raise HTTPException(404, f"Unknown question_id: {req.question_id}")
    true_answer = lookup["correct_answer"]

    is_correct, answer_detail = grade_answer(lookup["question_type"], req.selected_answer, true_answer)

    # Update knowledge model + log the response against this session.
    # Uses the QUESTION's own canonical_subject (req.subject), not
    # practice_category -- mastery/BKT params are still tracked at
    # subject granularity.
    updated_skill = KM.update_skill(
        student_id      = req.student_id,
        question_id     = req.question_id,
        concept_id      = req.concept_id,
        subject         = req.subject,
        topic           = req.topic,
        subtopic        = req.subtopic,
        difficulty      = req.difficulty,
        correct         = is_correct,
        session_id      = req.session_id,
        selected_answer = req.selected_answer,
        time_taken_sec  = req.time_taken_sec,
    )

    # Get next question -- same practice_category session.
    selector = get_selector()
    next_q   = selector.select_question(req.student_id, req.practice_category)

    # Mastery label
    score = updated_skill["skill_score"]
    if score >= 0.80:
        mastery_label = "Mastered ✅"
    elif score >= 0.60:
        mastery_label = "Proficient 🟡"
    elif score >= 0.40:
        mastery_label = "Developing 🟠"
    else:
        mastery_label = "Needs Practice 🔴"

    return {
        "correct":         is_correct,
        "correct_answer":  true_answer,   # fine to REVEAL now that the response is scored --
                                           # this is feedback, not the pre-answer key
        "answer_detail":   answer_detail, # None for single-answer types; for multi_select,
                                           # {status: "correct"|"partial"|"incorrect",
                                           #  correct_options, selected_options,
                                           #  missed_options, extra_options} -- lets the
                                           # frontend show a nuanced partial-credit message
                                           # even though `correct` above is strictly
                                           # exact-set-match (no partial credit in BKT).
        "updated_skill": {
            "concept_id":    req.concept_id,
            "topic":         req.topic,
            "subtopic":      req.subtopic,
            "bkt_score":     round(updated_skill["bkt_score"], 3),
            "ema_score":     round(updated_skill["ema_score"], 3),
            "skill_score":   round(updated_skill["skill_score"], 3),
            "mastery_label": mastery_label,
            "attempts":      updated_skill["attempts"],
        },
        "next_question": (
            {k: (v if v == v else None) for k, v in next_q.items() if k != "correct_answer"}
            if next_q else None
        )
    }


@router.get("/student/{student_id}/summary")
def student_summary(student_id: str, subject: Optional[str] = None):
    """Full mastery summary for a student, optionally filtered by
    canonical_subject. Dashboard/reporting -- deliberately subject-scoped,
    not practice_category-scoped."""
    if subject:
        summaries = [KM.get_subject_summary(student_id, subject)]
    else:
        subjects = QUESTIONS_DF["canonical_subject"].dropna().unique().tolist()
        summaries = [KM.get_subject_summary(student_id, s) for s in subjects]

    return {"student_id": student_id, "subjects": summaries}


@router.get("/student/{student_id}/skills")
def student_skills(student_id: str, subject: str):
    """Detailed per-concept skill scores for a student in one canonical_subject."""
    skills = KM.get_all_skills(student_id, subject)
    coverage = get_selector().get_coverage_stats(student_id, subject)

    return {
        "student_id": student_id,
        "subject":    subject,
        "coverage":   coverage,
        "skills":     sorted(skills, key=lambda x: x["skill_score"])
    }


@router.get("/student/{student_id}/history")
def student_history(student_id: str, n: int = 20):
    """Recent interaction log."""
    history = KM.get_recent_history(student_id, n)
    return {"student_id": student_id, "history": history}


@router.get("/dag/{subject}")
def get_dag(subject: str):
    """Return the concept graph for one canonical_subject (for
    visualization). Deliberately subject-scoped, not category-scoped --
    a whole category's graph (500-1500+ concepts) is too big to be a
    useful single visualization."""
    nodes = []
    edges = []
    for cid, node in DAG.nodes.items():
        if node.subject == subject:
            nodes.append({
                "id": cid, "topic": node.topic, "subtopic": node.subtopic
            })
            for dep in node.dependents:
                if dep in DAG.nodes and DAG.nodes[dep].subject == subject:
                    edges.append({"from": cid, "to": dep})
    return {"subject": subject, "nodes": nodes, "edges": edges}
