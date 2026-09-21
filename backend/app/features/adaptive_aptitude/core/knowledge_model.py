"""
knowledge_model.py
------------------
Student Knowledge Model with two tracking methods:

1. Bayesian Knowledge Tracing (BKT)
   - Per-concept probability P(learned) that updates with each answer
   - Parameters: p_init, p_transit, p_slip, p_guess
   - Classic EDM model, well-studied in the literature (e.g. on ASSISTments
     data by other researchers) -- but SUBJECT_BKT_PARAMS below is fit to
     THIS platform's own data via scripts/sweep_bkt_params.py, not borrowed
     from that literature; see the comment above SUBJECT_BKT_PARAMS.

2. Exponential Moving Average (EMA)
   - Lightweight alternative, good for fast updates
   - Smoothed accuracy score per concept

Both methods update the Student_Skill table after every answered question.
"""

import math
import json
import sqlite3
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List, Tuple
from datetime import datetime


# ── BKT Parameters (defaults tuned on ASSISTments data) ───────────────────

@dataclass
class BKTParams:
    """
    p_init    : P(student already knows concept at start)
    p_transit : P(transitions from not-knowing to knowing after each attempt)
    p_slip    : P(answers wrong despite knowing — careless error)
    p_guess   : P(answers correctly despite not knowing — lucky guess)
    """
    p_init:     float = 0.30
    p_transit:  float = 0.09
    p_slip:     float = 0.10
    p_guess:    float = 0.20


# Placeholder BKT params per subject. Historically commented as "empirically
# tuned from ASSISTments literature" -- that claim was never actually true:
# no ASSISTments (or any other real interaction) data was ever loaded into
# this project (data/dataset_loader.py's load_assistments()/
# estimate_bkt_params_from_data() exist but are dead code, never called
# anywhere, and no ASSISTments CSV file or output was ever present in this
# repo). Treat the numbers below as borrowed starting guesses, not validated
# literature values -- and note ASSISTments (US K-12 math tutoring logs)
# is a different population/domain from GATE-level engineering/CS aptitude
# content anyway, so even a real ASSISTments fit wouldn't necessarily
# transfer here.
#
# The values ARE now being superseded, subject by subject, by
# `python scripts/sweep_bkt_params.py` -- which empirically fits
# (p_init, p_transit, p_slip, p_guess) against THIS platform's own question
# bank, evaluated for calibration_error against two internally-consistent
# simulators (see experiments/simulators.py). That's real, reproducible,
# domain-matched evidence, and is the citable basis for these numbers going
# forward -- cite reports/phase1/ and the sweep methodology in the paper,
# not "ASSISTments literature".
#
# IMPORTANT: keys here MUST exactly match `canonical_subject` values in the
# `concepts` table (see reports/canonical_subject_mapping.json /
# `SELECT DISTINCT canonical_subject FROM concepts`), not the raw label
# strings that existed before Phase 0's canonicalization. A silent typo
# here doesn't error -- SUBJECT_BKT_PARAMS.get(subject, BKTParams())
# quietly falls back to the generic default, so every subject below was
# fact-checked against the real 22 canonical_subject values as of this fix
# (previously "Operating System", "Programming and Data Structure", and
# "Mathematics" didn't match anything real and were silently getting the
# generic default the whole time). Run
# `python scripts/check_bkt_param_coverage.py` after any change to this
# dict or to canonical_subject_mapping.json to catch this class of bug
# before it silently reoccurs.
#
# Subjects NOT listed here intentionally use the generic BKTParams()
# default -- there is no ASSISTments-literature basis to invent numbers
# for them, and fabricating "empirically tuned" values with nothing behind
# them would be worse than an honest, visible default. Once real pilot
# data exists (see the Phase 1 plan), re-tuning ALL of these -- including
# the ones below, which are still borrowed from a different population/
# subject domain -- from actual student responses should replace this
# entire dict.
SUBJECT_BKT_PARAMS: Dict[str, BKTParams] = {

    # Aptitude -- swept via BKTOnlyFocusedSelector, mean_calib=0.0756, mean_roc_auc=0.6106
    "General Aptitude":                        BKTParams(0.30, 0.10, 0.08, 0.25),

    # Core CS (Systems & Theory) -- swept mean_calib=0.0739, mean_roc_auc=0.5688
    # (applied uniformly across all 13 subjects in this category -- see
    # sweep_bkt_params.py docstring "NOTE ON GRANULARITY")
    "Compiler Design":                         BKTParams(0.30, 0.10, 0.15, 0.25),
    "Computer Organization and Architecture":  BKTParams(0.30, 0.10, 0.15, 0.25),
    "Computer Networks":                       BKTParams(0.30, 0.10, 0.15, 0.25),
    "Databases":                                BKTParams(0.30, 0.10, 0.15, 0.25),
    "Software Engineering":                    BKTParams(0.30, 0.10, 0.15, 0.25),
    "Cybersecurity":                            BKTParams(0.30, 0.10, 0.15, 0.25),
    "Cloud Computing":                          BKTParams(0.30, 0.10, 0.15, 0.25),
    "System Software":                          BKTParams(0.30, 0.10, 0.15, 0.25),
    "Operating Systems":                        BKTParams(0.30, 0.10, 0.15, 0.25),
    "Web Technologies":                         BKTParams(0.30, 0.10, 0.15, 0.25),
    "Computer Science (Miscellaneous)":         BKTParams(0.30, 0.10, 0.15, 0.25),
    "Digital Logic":                            BKTParams(0.30, 0.10, 0.15, 0.25),
    "Theory of Computation":                    BKTParams(0.30, 0.10, 0.15, 0.25),

    # Data Science & AI -- swept mean_calib=0.0878, mean_roc_auc=0.5505
    "Artificial Intelligence":                  BKTParams(0.30, 0.15, 0.15, 0.25),
    "Operations Research":                      BKTParams(0.30, 0.15, 0.15, 0.25),
    "Data Mining and Warehousing":               BKTParams(0.30, 0.15, 0.15, 0.25),
    "Big Data Systems":                         BKTParams(0.30, 0.15, 0.15, 0.25),

    # Engineering Mathematics -- swept mean_calib=0.0745, mean_roc_auc=0.5751
    "Engineering Mathematics":                  BKTParams(0.30, 0.05, 0.15, 0.25),
    "Discrete Mathematics":                     BKTParams(0.30, 0.05, 0.15, 0.25),

    # Programming & DSA -- swept mean_calib=0.0769, mean_roc_auc=0.5538
    "Algorithms":                               BKTParams(0.30, 0.10, 0.15, 0.25),
    "Programming and Data Structures":          BKTParams(0.30, 0.10, 0.15, 0.25),
}
# All 22 canonical_subject values are now covered (previously only 9 were,
# with the other 13 silently getting the generic BKTParams() default with
# nothing behind it -- see reports/practice_category_mapping.json for the
# category membership these were pulled from). Run
# `python scripts/check_bkt_param_coverage.py` after any change here.


# ── Core BKT Update ────────────────────────────────────────────────────────

def bkt_update(p_known: float, correct: bool, params: BKTParams) -> float:
    """
    Standard BKT update step.

    Args:
        p_known : Current P(learned) for this concept
        correct : Whether the student answered correctly
        params  : BKT parameters for this subject

    Returns:
        Updated P(learned)
    """
    # Step 1: P(correct) given current knowledge state
    if correct:
        p_obs = (p_known * (1 - params.p_slip)) + ((1 - p_known) * params.p_guess)
    else:
        p_obs = (p_known * params.p_slip) + ((1 - p_known) * (1 - params.p_guess))

    p_obs = max(p_obs, 1e-9)  # avoid division by zero

    # Step 2: Posterior — P(known | observation)
    if correct:
        p_known_given_obs = (p_known * (1 - params.p_slip)) / p_obs
    else:
        p_known_given_obs = (p_known * params.p_slip) / p_obs

    # Step 3: Learning transition
    p_known_next = p_known_given_obs + (1 - p_known_given_obs) * params.p_transit

    return min(max(p_known_next, 0.0), 1.0)


def ema_update(current_score: float, correct: bool, alpha: float = 0.3) -> float:
    """
    Exponential Moving Average mastery update.
    alpha controls how much weight to give to the new observation.
    Higher alpha = faster adaptation to recent performance.
    """
    new_obs = 1.0 if correct else 0.0
    return alpha * new_obs + (1 - alpha) * current_score


# ── Student Knowledge Model ────────────────────────────────────────────────

class StudentKnowledgeModel:
    """
    Manages all student mastery scores.
    Stores in SQLite for persistence.
    """

    MASTERY_THRESHOLD = 0.80   # P(known) >= this → concept is mastered
    EMA_ALPHA = 0.30           # EMA smoothing factor

    def __init__(self, db_path: str = "adaptive_platform.db"):
        self.db_path = db_path
        self._init_db()

    # ── Database setup ─────────────────────────────────────────────────────

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS student_skill (
                    student_id      TEXT NOT NULL,
                    concept_id      TEXT NOT NULL,
                    subject         TEXT NOT NULL,
                    topic           TEXT NOT NULL,
                    subtopic        TEXT NOT NULL,
                    bkt_score       REAL DEFAULT 0.3,
                    ema_score       REAL DEFAULT 0.5,
                    skill_score     REAL DEFAULT 0.3,
                    attempts        INTEGER DEFAULT 0,
                    correct_count   INTEGER DEFAULT 0,
                    last_updated    TEXT,
                    PRIMARY KEY (student_id, concept_id)
                );

                CREATE TABLE IF NOT EXISTS interaction_log (
                    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id      TEXT NOT NULL,
                    question_id     TEXT NOT NULL,
                    concept_id      TEXT NOT NULL,
                    subject         TEXT NOT NULL,
                    topic           TEXT NOT NULL,
                    subtopic        TEXT NOT NULL,
                    difficulty      TEXT,
                    correct         INTEGER NOT NULL,
                    time_taken_sec  REAL,
                    bkt_before      REAL,
                    bkt_after       REAL,
                    ema_before      REAL,
                    ema_after       REAL,
                    timestamp       TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS student_session (
                    session_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id      TEXT NOT NULL,
                    subject         TEXT NOT NULL,
                    start_time      TEXT NOT NULL,
                    end_time        TEXT,
                    questions_asked INTEGER DEFAULT 0,
                    correct_count   INTEGER DEFAULT 0
                );
            """)

    # ── Get/Initialize skill ───────────────────────────────────────────────

    def get_skill(self, student_id: str, concept_id: str,
                  subject: str = "", topic: str = "", subtopic: str = "") -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM student_skill WHERE student_id=? AND concept_id=?",
                (student_id, concept_id)
            ).fetchone()

        if row:
            return dict(row)

        # Initialize new skill record
        params = SUBJECT_BKT_PARAMS.get(subject, BKTParams())
        return {
            "student_id": student_id, "concept_id": concept_id,
            "subject": subject, "topic": topic, "subtopic": subtopic,
            "bkt_score": params.p_init, "ema_score": 0.5,
            "skill_score": params.p_init,
            "attempts": 0, "correct_count": 0,
            "last_updated": None
        }

    def get_all_skills(self, student_id: str, subject: Optional[str] = None) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if subject:
                rows = conn.execute(
                    "SELECT * FROM student_skill WHERE student_id=? AND subject=?",
                    (student_id, subject)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM student_skill WHERE student_id=?",
                    (student_id,)
                ).fetchall()
        return [dict(r) for r in rows]

    def get_mastery_dict(self, student_id: str, subject: str) -> Dict[str, float]:
        """Returns {concept_id: skill_score} for all known concepts in subject."""
        skills = self.get_all_skills(student_id, subject)
        return {s["concept_id"]: s["skill_score"] for s in skills}

    def get_mastery_dict_all(self, student_id: str) -> Dict[str, float]:
        """Returns {concept_id: skill_score} across EVERY subject this student
        has ever touched, not just one. Use this (not get_mastery_dict) for
        DAG unlock checks -- a concept's prerequisite can live in a
        DIFFERENT subject than the one currently being practiced (e.g. a
        Discrete Mathematics concept gating an Artificial Intelligence one).
        get_mastery_dict's subject filter would make such a prerequisite
        look permanently unmastered (default 0.0) regardless of the
        student's real mastery of it, silently locking the dependent
        concept forever -- exactly the bug found and fixed in
        experiments/selectors/mastery_based.py's MasteryBasedSelector.select();
        this is the same fix applied to the production path."""
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
                     time_taken_sec: float = 0.0) -> dict:
        """
        Update student mastery after answering a question.
        Returns the updated skill record.
        """
        skill = self.get_skill(student_id, concept_id, subject, topic, subtopic)
        params = SUBJECT_BKT_PARAMS.get(subject, BKTParams())

        bkt_before = skill["bkt_score"]
        ema_before = skill["ema_score"]

        # Apply updates
        bkt_after = bkt_update(bkt_before, correct, params)
        ema_after = ema_update(ema_before, correct, self.EMA_ALPHA)

        # Combined skill score: weighted average of BKT and EMA
        skill_score = 0.6 * bkt_after + 0.4 * ema_after

        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # Upsert skill record
            conn.execute("""
                INSERT INTO student_skill
                    (student_id, concept_id, subject, topic, subtopic,
                     bkt_score, ema_score, skill_score, attempts, correct_count, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id, concept_id) DO UPDATE SET
                    bkt_score     = excluded.bkt_score,
                    ema_score     = excluded.ema_score,
                    skill_score   = excluded.skill_score,
                    attempts      = student_skill.attempts + 1,
                    correct_count = student_skill.correct_count + ?,
                    last_updated  = excluded.last_updated
            """, (
                student_id, concept_id, subject, topic, subtopic,
                bkt_after, ema_after, skill_score,
                skill["attempts"] + 1,
                skill["correct_count"] + (1 if correct else 0),
                now,
                1 if correct else 0
            ))

            # Log the interaction
            conn.execute("""
                INSERT INTO interaction_log
                    (student_id, question_id, concept_id, subject, topic, subtopic,
                     difficulty, correct, time_taken_sec,
                     bkt_before, bkt_after, ema_before, ema_after, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                student_id, question_id, concept_id, subject, topic, subtopic,
                difficulty, int(correct), time_taken_sec,
                bkt_before, bkt_after, ema_before, ema_after, now
            ))

        return self.get_skill(student_id, concept_id)

    # ── Query helpers ──────────────────────────────────────────────────────

    def is_mastered(self, student_id: str, concept_id: str, subject: str) -> bool:
        skill = self.get_skill(student_id, concept_id, subject)
        return skill["skill_score"] >= self.MASTERY_THRESHOLD

    def get_weak_concepts(self, student_id: str, subject: str,
                           threshold: float = 0.5) -> List[str]:
        """Concepts that need more practice (below threshold)."""
        mastery = self.get_mastery_dict(student_id, subject)
        return [cid for cid, score in mastery.items() if score < threshold]

    def get_recent_history(self, student_id: str, n: int = 20) -> List[dict]:
        """Last n interactions for this student."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM interaction_log WHERE student_id=? ORDER BY timestamp DESC LIMIT ?",
                (student_id, n)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recently_seen_questions(self, student_id: str, n: int = 50) -> set:
        """Avoid repeating questions student has seen recently."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT question_id FROM interaction_log WHERE student_id=? ORDER BY timestamp DESC LIMIT ?",
                (student_id, n)
            ).fetchall()
        return {r[0] for r in rows}

    def get_last_attempted_concept(self, student_id: str, subject: str) -> Optional[str]:
        """Most recent concept_id this student was asked a question on,
        within `subject`, or None if they haven't started. Used by
        concept-focus selection (QuestionSelector._select_focus_concept) to
        recover "what was I just drilling" across stateless HTTP requests,
        without needing a new table -- interaction_log already has this."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT concept_id FROM interaction_log WHERE student_id=? AND subject=? "
                "ORDER BY timestamp DESC LIMIT 1",
                (student_id, subject)
            ).fetchone()
        return row[0] if row else None

    def get_subject_summary(self, student_id: str, subject: str) -> dict:
        """Overall performance summary for a subject."""
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
            "total_concepts": len(skills),
            "total_attempts": total_attempts,
            "accuracy":       round(total_correct / total_attempts, 3) if total_attempts else 0.0
        }
