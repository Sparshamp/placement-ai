"""
core/knowledge_model_pg.py
---------------------------
Postgres-backed replacement for StudentKnowledgeModel (core/knowledge_model.py),
which stores mastery/session/response data in SQLite (adaptive_platform.db).
Uses the student_sessions / student_responses / student_mastery tables
db/schema_extended.sql already defines, instead of ad-hoc SQLite tables
that don't match that schema (no session linkage on responses, no FK to a
real students table, canonical_subject/topic/subtopic duplicated onto every
row instead of resolved from `concepts` at read time).

DROP-IN REPLACEMENT: every method here has the exact same name, signature,
and return shape (list-of-dict / dict-of-float) as the SQLite
StudentKnowledgeModel it replaces. QuestionSelector and api/main.py were
written against that interface and need ZERO changes beyond which class
gets instantiated -- see api/main.py's `KM = ...` line. This mirrors the
same "keep the interface, swap the backend" approach used for the DAG/
question-pool rewire in experiments/data.py.

KEY SCHEMA DIFFERENCE FROM SQLITE: student_mastery does NOT duplicate
subject/topic/subtopic onto every mastery row (unlike SQLite's
student_skill table) -- it only stores concept_id, joining against
`concepts` at read time to resolve canonical_subject/canonical_topic/
subtopic, consistent with how questions_resolved itself works. This
means get_all_skills/get_mastery_dict etc. all JOIN concepts rather than
filtering a denormalized column, but the returned dict shape is identical
to the SQLite version so callers don't see the difference.

SESSION-SCOPED WRITES: student_responses.session_id is NOT NULL with a
real FK to student_sessions -- unlike SQLite's interaction_log, which
never linked a response to a session at all. This means update_skill()
now requires a real session_id (from start_session()), not optional.
api/main.py threads this through: /session/start creates the row and
returns its real UUID; /question/answer requires the client to send it
back, same as practice_category (see api/main.py AnswerRequest).
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

# from data.db_loader import get_engine
from app.features.adaptive_aptitude.data.db_loader import get_engine
# from core.knowledge_model import BKTParams, SUBJECT_BKT_PARAMS, bkt_update, ema_update
from app.features.adaptive_aptitude.core.knowledge_model import BKTParams, SUBJECT_BKT_PARAMS, bkt_update, ema_update


class PostgresStudentKnowledgeModel:

    MASTERY_THRESHOLD = 0.80
    EMA_ALPHA = 0.30

    def __init__(self):
        self.engine = get_engine()

    # ── Students / sessions ─────────────────────────────────────────────────

    def ensure_student(self, student_id: str) -> None:
        """Every write below has an FK to students.student_id -- insert it
        first if this is a new student. Idempotent."""
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO students (student_id) VALUES (%s) ON CONFLICT (student_id) DO NOTHING",
                (student_id,),
            )

    # def start_session(self, student_id: str, practice_category: str,
    #                    algorithm: str = "bkt_ema_epsilon_greedy_focused") -> str:
    #     """Create a real student_sessions row and return its UUID (as str).
    #     api/main.py's /session/start uses THIS as the session_id it hands
    #     back to the client -- unlike the previous SQLite version, which
    #     generated an unrelated uuid4() client-side that was never actually
    #     connected to the logged row."""
    #     self.ensure_student(student_id)
    #     with self.engine.begin() as conn:
    #         row = conn.exec_driver_sql(
    #             """
    #             INSERT INTO student_sessions (student_id, practice_category, algorithm)
    #             VALUES (%s, %s, %s)
    #             RETURNING session_id
    #             """,
    #             (student_id, practice_category, algorithm),
    #         ).fetchone()
    #     return str(row[0])

    def start_session(self, student_id: str, practice_category: str,
                    algorithm: str = "bkt_ema_epsilon_greedy_focused") -> str:
        """Create a real student_sessions row and return its UUID (as str).

        RETENTION: only the most recently started session's per-question
        responses are kept in student_responses -- starting a new session
        purges every response logged under this student's earlier
        sessions first. student_sessions rows themselves (and their
        questions_asked/correct_count rollups) are NOT deleted, only the
        granular student_responses log -- so /student/{id}/summary and
        /student/{id}/skills (which read student_mastery, not
        student_responses) are unaffected; only /student/{id}/history and
        the "avoid repeating a recent question" / "stay on the last
        concept" logic in QuestionSelector are now scoped to the current
        session instead of the student's full lifetime.
        """
        self.ensure_student(student_id)
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                "DELETE FROM student_responses WHERE student_id = %s",
                (student_id,),
            )
            row = conn.exec_driver_sql(
                """
                INSERT INTO student_sessions (student_id, practice_category, algorithm)
                VALUES (%s, %s, %s)
                RETURNING session_id
                """,
                (student_id, practice_category, algorithm),
            ).fetchone()
        return str(row[0])

    # ── Get/Initialize skill ───────────────────────────────────────────────

    def get_skill(self, student_id: str, concept_id: str,
                  subject: str = "", topic: str = "", subtopic: str = "") -> dict:
        with self.engine.connect() as conn:
            row = conn.exec_driver_sql(
                """
                SELECT sm.student_id, sm.concept_id, c.canonical_subject AS subject,
                       c.canonical_topic AS topic, c.subtopic,
                       sm.bkt_score, sm.ema_score, sm.skill_score,
                       sm.attempts, sm.correct_count, sm.last_updated
                FROM student_mastery sm
                JOIN concepts c ON c.concept_id = sm.concept_id
                WHERE sm.student_id = %s AND sm.concept_id = %s
                """,
                (student_id, concept_id),
            ).mappings().fetchone()

        if row:
            return dict(row)

        # No row yet -- initialize using this subject's tuned BKT prior,
        # same fallback behavior as the SQLite version.
        params = SUBJECT_BKT_PARAMS.get(subject, BKTParams())
        return {
            "student_id": student_id, "concept_id": concept_id,
            "subject": subject, "topic": topic, "subtopic": subtopic,
            "bkt_score": params.p_init, "ema_score": 0.5,
            "skill_score": params.p_init,
            "attempts": 0, "correct_count": 0,
            "last_updated": None,
        }

    def get_all_skills(self, student_id: str, subject: Optional[str] = None) -> List[dict]:
        query = """
            SELECT sm.student_id, sm.concept_id, c.canonical_subject AS subject,
                   c.canonical_topic AS topic, c.subtopic,
                   sm.bkt_score, sm.ema_score, sm.skill_score,
                   sm.attempts, sm.correct_count, sm.last_updated
            FROM student_mastery sm
            JOIN concepts c ON c.concept_id = sm.concept_id
            WHERE sm.student_id = %s
        """
        params = [student_id]
        if subject:
            query += " AND c.canonical_subject = %s"
            params.append(subject)

        with self.engine.connect() as conn:
            rows = conn.exec_driver_sql(query, tuple(params)).mappings().fetchall()
        return [dict(r) for r in rows]

    def get_mastery_dict(self, student_id: str, subject: str) -> Dict[str, float]:
        """Returns {concept_id: skill_score} for all known concepts in subject."""
        skills = self.get_all_skills(student_id, subject)
        return {s["concept_id"]: s["skill_score"] for s in skills}

    def get_mastery_dict_all(self, student_id: str) -> Dict[str, float]:
        """Returns {concept_id: skill_score} across EVERY subject this
        student has touched -- see StudentKnowledgeModel.get_mastery_dict_all
        for why this (not get_mastery_dict) is what DAG unlock checks need."""
        skills = self.get_all_skills(student_id, subject=None)
        return {s["concept_id"]: s["skill_score"] for s in skills}

    # ── Update after answer ────────────────────────────────────────────────

    def update_skill(self,
                      student_id: str,
                      question_id: str,
                      concept_id: str,
                      subject: str,
                      topic: str,
                      subtopic: str,
                      difficulty: str,
                      correct: bool,
                      session_id: str,
                      selected_answer: str = "",
                      time_taken_sec: float = 0.0) -> dict:
        """
        Update student mastery after answering a question, and log the
        response against a real session. Returns the updated skill record
        (same shape as get_skill).

        session_id is required (unlike the SQLite version, where responses
        had no session linkage at all) -- student_responses.session_id is
        NOT NULL with a real FK to student_sessions. Callers must have
        already called start_session() and threaded the returned id back
        in -- see api/main.py AnswerRequest.session_id.
        """
        self.ensure_student(student_id)
        skill = self.get_skill(student_id, concept_id, subject, topic, subtopic)
        params = SUBJECT_BKT_PARAMS.get(subject, BKTParams())

        bkt_before = skill["bkt_score"]
        ema_before = skill["ema_score"]

        bkt_after = bkt_update(bkt_before, correct, params)
        ema_after = ema_update(ema_before, correct, self.EMA_ALPHA)
        skill_score = 0.6 * bkt_after + 0.4 * ema_after

        mastery_before = {"bkt": bkt_before, "ema": ema_before, "skill_score": skill["skill_score"]}
        mastery_after = {"bkt": bkt_after, "ema": ema_after, "skill_score": skill_score}
        now = datetime.now(timezone.utc)

        with self.engine.begin() as conn:
            # Upsert mastery
            conn.exec_driver_sql(
                """
                INSERT INTO student_mastery
                    (student_id, concept_id, bkt_score, ema_score, skill_score,
                     attempts, correct_count, last_updated)
                VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
                ON CONFLICT (student_id, concept_id) DO UPDATE SET
                    bkt_score     = EXCLUDED.bkt_score,
                    ema_score     = EXCLUDED.ema_score,
                    skill_score   = EXCLUDED.skill_score,
                    attempts      = student_mastery.attempts + 1,
                    correct_count = student_mastery.correct_count + %s,
                    last_updated  = EXCLUDED.last_updated
                """,
                (
                    student_id, concept_id, bkt_after, ema_after, skill_score,
                    1 if correct else 0, now,
                    1 if correct else 0,
                ),
            )

            # Log the response against this session
            conn.exec_driver_sql(
                """
                INSERT INTO student_responses
                    (session_id, student_id, question_id, concept_id, difficulty_at_ask,
                     selected_answer, is_correct, time_taken_sec, mastery_before, mastery_after)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id, student_id, question_id, concept_id, difficulty,
                    selected_answer, bool(correct), time_taken_sec,
                    json.dumps(mastery_before), json.dumps(mastery_after),
                ),
            )

            # Keep the session-level rollup counters current -- nice to
            # have for a session-summary view later, not load-bearing for
            # selection/mastery itself.
            conn.exec_driver_sql(
                """
                UPDATE student_sessions
                SET questions_asked = questions_asked + 1,
                    correct_count   = correct_count + %s
                WHERE session_id = %s
                """,
                (1 if correct else 0, session_id),
            )

        return self.get_skill(student_id, concept_id, subject, topic, subtopic)

    # ── Query helpers ──────────────────────────────────────────────────────

    def is_mastered(self, student_id: str, concept_id: str, subject: str) -> bool:
        skill = self.get_skill(student_id, concept_id, subject)
        return skill["skill_score"] >= self.MASTERY_THRESHOLD

    def get_weak_concepts(self, student_id: str, subject: str,
                           threshold: float = 0.5) -> List[str]:
        mastery = self.get_mastery_dict(student_id, subject)
        return [cid for cid, score in mastery.items() if score < threshold]

    def get_recent_history(self, student_id: str, n: int = 20) -> List[dict]:
        with self.engine.connect() as conn:
            rows = conn.exec_driver_sql(
                """
                SELECT sr.response_id AS log_id, sr.student_id, sr.question_id, sr.concept_id,
                       c.canonical_subject AS subject, c.canonical_topic AS topic, c.subtopic,
                       sr.difficulty_at_ask AS difficulty, sr.is_correct AS correct,
                       sr.time_taken_sec, sr.mastery_before, sr.mastery_after,
                       sr.answered_at AS timestamp
                FROM student_responses sr
                LEFT JOIN concepts c ON c.concept_id = sr.concept_id
                WHERE sr.student_id = %s
                ORDER BY sr.answered_at DESC
                LIMIT %s
                """,
                (student_id, n),
            ).mappings().fetchall()
        return [dict(r) for r in rows]

    def get_recently_seen_questions(self, student_id: str, n: int = 50) -> set:
        with self.engine.connect() as conn:
            rows = conn.exec_driver_sql(
                """
                SELECT question_id FROM student_responses
                WHERE student_id = %s ORDER BY answered_at DESC LIMIT %s
                """,
                (student_id, n),
            ).fetchall()
        return {r[0] for r in rows}

    def get_last_attempted_concept_id(self, student_id: str) -> Optional[str]:
        """Most recent concept_id this student was asked ANY question on,
        regardless of subject/category -- see QuestionSelector._select_focus_concept
        for how the category check on top of this works."""
        with self.engine.connect() as conn:
            row = conn.exec_driver_sql(
                """
                SELECT concept_id FROM student_responses
                WHERE student_id = %s ORDER BY answered_at DESC LIMIT 1
                """,
                (student_id,),
            ).fetchone()
        return row[0] if row else None

    def get_subject_summary(self, student_id: str, subject: str) -> dict:
        skills = self.get_all_skills(student_id, subject)
        if not skills:
            return {"subject": subject, "concepts_seen": 0, "avg_mastery": 0.0,
                     "mastered_count": 0, "total_attempts": 0, "accuracy": 0.0}

        total_attempts = sum(s["attempts"] for s in skills)
        total_correct  = sum(s["correct_count"] for s in skills)
        mastered       = sum(1 for s in skills if s["skill_score"] >= self.MASTERY_THRESHOLD)
        avg_mastery    = sum(s["skill_score"] for s in skills) / len(skills)

        return {
            "subject":        subject,
            "concepts_seen":  len(skills),
            "avg_mastery":    round(avg_mastery, 3),
            "mastered_count": mastered,
            "total_attempts": total_attempts,
            "accuracy":       round(total_correct / total_attempts, 3) if total_attempts else 0.0,
        }
