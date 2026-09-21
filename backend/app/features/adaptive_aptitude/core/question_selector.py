"""
question_selector.py
--------------------
Selects the next best question for a student using a combination of:

1. Concept DAG constraints  — don't test advanced concepts before prerequisites
2. BKT/EMA mastery scores   — target weak concepts (exploit)
3. Exploration              — occasionally probe new/unseen concepts (explore)
4. Difficulty progression   — match question difficulty to current mastery
5. Recency filter           — avoid repeating recently seen questions

Selection Strategy (concept-FOCUS, validated in Phase 1 -- see
reports/phase1/ and experiments/selectors/mastery_based.py):
  - Stay on ONE concept across consecutive questions until it's mastered,
    given up on (attempt cap), or out of unseen questions -- THEN pick a
    new concept via epsilon-greedy explore/exploit, same as before.
  - Within the current focus concept: pick a question whose difficulty
    matches current mastery level.
  This beat the old "pick a (possibly new) concept every single question"
  roaming policy on ROC-AUC in all 5 practice categories under both Phase 1
  simulators (see reports/phase1/cross_simulator_ranking_*.md) -- roaming
  spreads a session too thin across a 2,500+-concept DAG for BKT/EMA to
  ever get enough repeated observations per concept to actually learn
  anything (questions_to_mastery was literally NaN under roaming for the
  BKT-based trackers). Set focus_until_mastered=False on a QuestionSelector
  instance to fall back to the old roaming behavior if ever needed for
  comparison.

DATA SOURCE: expects questions_df shaped like the `questions_resolved`
Postgres view (data/db_loader.py / experiments/data.py) -- i.e. already
carrying canonical_subject, canonical_topic, subtopic, concept_id,
practice_category columns from Phase 0's canonicalization, not just the
raw `questions` table's subject/topic/subtopic strings (questions_resolved
keeps both -- q.* plus the canonical_* columns -- this module always reads
the canonical ones). Uses the real `question_id` primary-key column
directly; no more `question_index` alias (that was a `data/db_loader.py`
compatibility shim for the old raw-table loader and no longer applies).

concept_dag should be built via experiments.data.load_concept_dag() (the
real ~2,539-concept Postgres-backed DAG), not core.concept_dag.
build_default_dag() (a ~17-node hand-authored Computer Networks demo that
predates Phase 0 and doesn't match the real subject/topic/subtopic label
space -- see the very first project review for how badly those mismatched).
"""

import random
import math
from typing import List, Dict, Optional, Set
import pandas as pd


# ── Difficulty mapping ─────────────────────────────────────────────────────

DIFFICULTY_MASTERY_BANDS = {
    # mastery range → appropriate difficulty
    (0.00, 0.40): "Easy",
    (0.40, 0.70): "Medium",
    (0.70, 1.00): "Hard",
}

def mastery_to_difficulty(mastery: float) -> str:
    for (low, high), diff in DIFFICULTY_MASTERY_BANDS.items():
        if low <= mastery < high:
            return diff
    return "Medium"


# ── Concept scoring ────────────────────────────────────────────────────────

def score_concept_for_student(concept_id: str, mastery: float,
                               attempts: int, is_unlocked: bool) -> float:
    """
    Score how urgently a concept needs practice.
    Higher score = more likely to be selected.

    Factors:
    - Low mastery → higher priority (weak concepts need drilling)
    - Moderate attempts → slight boost (engagement signal)
    - Unlocked by prerequisites → eligible
    """
    if not is_unlocked:
        return -1.0  # not eligible

    # Urgency: inverse of mastery — weakest concepts score highest
    urgency = 1.0 - mastery

    # Bonus for concepts seen but not mastered (need reinforcement)
    reinforcement = 0.2 if 0 < attempts < 5 else 0.0

    # Bonus for never-seen concepts (encourage breadth)
    novelty = 0.15 if attempts == 0 else 0.0

    return urgency + reinforcement + novelty


# ── Main Question Selector ─────────────────────────────────────────────────

class QuestionSelector:

    # Concept-FOCUS mode, see module docstring. Validated in Phase 1 --
    # this is the default now, not an experimental opt-in.
    focus_until_mastered: bool = True
    mastery_threshold_mastered: float = 0.75   # higher bar than mastery_threshold_unlock (0.60) --
                                                # "unlocked" = good enough to build on,
                                                # "mastered" = stop drilling, move on
    max_focus_attempts: int = 8                # give-up cap per concept per focus streak

    def __init__(self,
                 questions_df: pd.DataFrame,
                 concept_dag,
                 knowledge_model,
                 epsilon: float = 0.20):
        """
        Args:
            questions_df   : Question pool DataFrame, shaped like
                              `questions_resolved` (canonical_subject,
                              canonical_topic, subtopic, concept_id,
                              practice_category, question_id columns
                              already present).
            concept_dag    : ConceptDAG instance, built from the real
                              Postgres concepts/concept_dependencies tables
                              (experiments.data.load_concept_dag()), not
                              build_default_dag().
            knowledge_model: StudentKnowledgeModel instance
            epsilon        : Exploration probability (0.0–1.0)
        """
        self.questions  = questions_df
        self.dag        = concept_dag
        self.km         = knowledge_model
        self.epsilon    = epsilon

        # Safety net only: if a caller passes an older, non-canonicalized
        # DataFrame that genuinely lacks concept_id (e.g. the raw
        # `questions` table with no join applied), fall back to guessing
        # from subject/topic/subtopic strings against the DAG, same as
        # before. With questions_resolved as input this branch should
        # never fire -- concept_id is already a real column, joined in
        # Postgres from subtopic_concept_map.
        if "concept_id" not in self.questions.columns:
            self.questions = self.questions.copy()
            self.questions["concept_id"] = self._infer_concept_ids()

        self._subject_col = "canonical_subject" if "canonical_subject" in self.questions.columns else "subject"
        # Selection path (select_question and everything it calls) is scoped
        # by practice_category, not canonical_subject -- see module
        # docstring. get_coverage_stats() is the one method that genuinely
        # stays subject-scoped (matches /student/{id}/skills's real
        # canonical_subject parameter), so _subject_col is kept for that.
        self._category_col = "practice_category"
        self._id_col = "question_id" if "question_id" in self.questions.columns else "question_index"

    def _infer_concept_ids(self) -> pd.Series:
        """Map (subject, topic, subtopic) → concept_id using the DAG.
        Fallback only -- see __init__ docstring. Not exercised when
        questions_df already carries a real concept_id column."""
        lookup = {}
        for cid, node in self.dag.nodes.items():
            key = (node.subject, node.topic, node.subtopic)
            lookup[key] = cid

        def map_row(row):
            key = (row["subject"], row["topic"], row["subtopic"])
            return lookup.get(key, f"UNKNOWN::{row['topic']}::{row['subtopic']}")

        return self.questions.apply(map_row, axis=1)

    # ── Main selection entry point ─────────────────────────────────────────

    def select_question(self, student_id: str, practice_category: str,
                         session_history: Optional[List[str]] = None) -> Optional[dict]:
        """
        Select the single best next question for this student in this
        practice_category session.

        practice_category is one of the 5 session-scoping buckets (e.g.
        "Core CS (Systems & Theory)"), matching questions_resolved.
        practice_category / ConceptDAG node.practice_category -- NOT a
        canonical_subject. api/main.py's session endpoints pass their
        req.practice_category straight through here. BUG FIX (Phase 2
        review): this used to call the SUBJECT-scoped DAG/question-pool
        methods even though it was being handed a practice_category value
        -- get_concepts_by_subject("Core CS (Systems & Theory)") always
        returned [] since no concept's .subject field ever equals a
        practice_category string, so every session-scoped call silently
        found zero questions. Fixed to use the category-scoped DAG methods
        and filter the question pool by practice_category, mirroring
        experiments/selectors/mastery_based.py's MasteryBasedSelector.select()
        exactly (that version was already correct -- this port had drifted
        from it).

        Returns a dict with question data, or None if no suitable question found.
        """
        session_history = session_history or []
        recently_seen   = self.km.get_recently_seen_questions(student_id, n=50)
        all_seen        = recently_seen | set(session_history)

        # Unscoped across ALL subjects this student has touched, not just
        # this category -- a concept's prerequisite can live in a
        # different category (e.g. Discrete Mathematics gating Artificial
        # Intelligence). See StudentKnowledgeModel.get_mastery_dict_all
        # docstring for why this (not a category-filtered dict) is needed.
        mastery_dict = self.km.get_mastery_dict_all(student_id)
        # Also unscoped (subject=None): "attempts" bookkeeping for
        # _exploit()'s reinforcement/novelty bonus needs every concept the
        # student has ever touched, not just ones matching this literal
        # practice_category string against canonical_subject (which would
        # always be empty for the same reason as the DAG bug above).
        skills = {s["concept_id"]: s for s in self.km.get_all_skills(student_id, subject=None)}

        # Get concepts whose prerequisites are satisfied
        all_concepts = self.dag.get_concepts_by_practice_category(practice_category)
        unlocked = set(self.dag.get_unlocked_concepts_in(all_concepts, mastery_dict, mastery_threshold=0.6))

        if self.focus_until_mastered:
            target_concept = self._select_focus_concept(
                student_id, practice_category, all_concepts, unlocked, mastery_dict, skills, all_seen
            )
        else:
            target_concept = self._select_roaming_concept(all_concepts, mastery_dict, skills, unlocked)

        if target_concept is None:
            return None

        # ── Select question for chosen concept ────────────────────────────
        mastery   = mastery_dict.get(target_concept, 0.3)
        target_diff = mastery_to_difficulty(mastery)

        question = self._pick_question(target_concept, practice_category, target_diff, all_seen)

        if question is None:
            # Relax difficulty constraint
            question = self._pick_question(target_concept, practice_category, difficulty=None,
                                           exclude_ids=all_seen)

        if question is None:
            # Last resort: any question in this category not yet seen
            category_qs = self.questions[
                (self.questions[self._category_col] == practice_category) &
                (~self.questions[self._id_col].astype(str).isin(all_seen))
            ]
            if not category_qs.empty:
                question = category_qs.sample(1).iloc[0].to_dict()

        return question

    # ── Roaming policy (original: pick a concept fresh every call) ─────────

    def _select_roaming_concept(self, concepts: List[str], mastery: Dict[str, float],
                                 skills: dict, unlocked: set) -> Optional[str]:
        if random.random() < self.epsilon:
            target_concept = self._explore(concepts, mastery, unlocked)
        else:
            target_concept = self._exploit(concepts, mastery, skills, unlocked)

        if target_concept is None:
            target_concept = (
                random.choice(list(unlocked)) if unlocked
                else (random.choice(concepts) if concepts else None)
            )
        return target_concept

    # ── Focus policy (validated in Phase 1, see module docstring) ──────────

    def _select_focus_concept(self, student_id: str, practice_category: str, all_concepts: List[str],
                               unlocked: set, mastery: Dict[str, float], skills: dict,
                               all_seen: Set[str]) -> Optional[str]:
        """Stay on the most-recently-attempted concept (recovered from
        interaction_log via get_last_attempted_concept, since production
        requests are stateless -- see that method's docstring) until it's
        mastered, given up on, or out of unseen questions. Only then pick a
        new concept via the same explore/exploit logic as the roaming
        policy. Mirrors experiments/selectors/mastery_based.py
        MasteryBasedSelector._select_focus_concept."""
        focus_concept = self.km.get_last_attempted_concept_id(student_id)

        attempts = skills.get(focus_concept, {}).get("attempts", 0) if focus_concept else 0
        still_valid = (
            focus_concept is not None
            and focus_concept in unlocked
            and mastery.get(focus_concept, 0.0) < self.mastery_threshold_mastered
            and attempts < self.max_focus_attempts
            and self._has_unseen_question(focus_concept, practice_category, all_seen)
        )
        if still_valid:
            return focus_concept

        # Not valid (mastered / given up / exhausted / never started) --
        # pick a new concept, excluding the one we're leaving so we don't
        # immediately re-select it via explore/exploit this same call.
        candidate_concepts = [c for c in all_concepts if c != focus_concept]
        candidate_unlocked = unlocked - {focus_concept} if focus_concept else unlocked

        new_target = self._select_roaming_concept(candidate_concepts, mastery, skills, candidate_unlocked)

        if new_target is None and focus_concept is not None:
            # Nothing else left to focus on this session (small subject,
            # everything mastered/exhausted) -- reopen the one we just left.
            # _pick_question's own fallback cascade still applies underneath
            # if even that has nothing left.
            new_target = focus_concept

        return new_target

    def _has_unseen_question(self, concept_id: str, practice_category: str, exclude_ids: Set[str]) -> bool:
        mask = (
            (self.questions["concept_id"] == concept_id)
            & (self.questions[self._category_col] == practice_category)
            & (~self.questions[self._id_col].astype(str).isin(exclude_ids))
        )
        return bool(mask.any())

    # ── Explore: pick a concept not yet studied or rarely studied ──────────

    def _explore(self, concepts: List[str], mastery: Dict[str, float],
                  unlocked: set) -> Optional[str]:
        """
        Exploration: prefer unseen or rarely attempted concepts among unlocked ones.
        """
        unseen  = [c for c in concepts if c not in mastery and c in unlocked]
        if unseen:
            return random.choice(unseen)

        # Pick lowest-mastery unlocked concept as fallback exploration
        unlocked_list = [(c, mastery.get(c, 0.0)) for c in concepts if c in unlocked]
        if not unlocked_list:
            return None
        unlocked_list.sort(key=lambda x: x[1])
        # Pick randomly from bottom 30%
        bottom_n = max(1, len(unlocked_list) // 3)
        return random.choice(unlocked_list[:bottom_n])[0]

    # ── Exploit: pick concept most in need of drilling ─────────────────────

    def _exploit(self, concepts: List[str], mastery: Dict[str, float],
                  skills: dict, unlocked: set) -> Optional[str]:
        """
        Exploitation: pick the unlocked concept with lowest mastery (needs most work).
        """
        scored = []
        for cid in concepts:
            m        = mastery.get(cid, 0.3)
            attempts = skills.get(cid, {}).get("attempts", 0)
            score    = score_concept_for_student(cid, m, attempts, cid in unlocked)
            if score >= 0:
                scored.append((cid, score))

        if not scored:
            return None

        # Softmax sampling — weighted by score (not pure greedy)
        scores = [s for _, s in scored]
        total  = sum(math.exp(s * 3) for s in scores)  # temperature = 3
        probs  = [math.exp(s * 3) / total for s in scores]

        concepts_list = [c for c, _ in scored]
        return random.choices(concepts_list, weights=probs, k=1)[0]

    # ── Pick an actual question row ────────────────────────────────────────

    def _pick_question(self, concept_id: str, practice_category: str,
                        difficulty: Optional[str],
                        exclude_ids: set) -> Optional[dict]:
        """
        Find a question for the given concept, within this practice_category,
        at this difficulty, that hasn't been seen.
        """
        mask = (self.questions["concept_id"] == concept_id) & \
               (self.questions[self._category_col] == practice_category)

        if difficulty:
            mask = mask & (self.questions["difficulty"] == difficulty)

        candidates = self.questions[mask]

        # Exclude already-seen questions
        if exclude_ids:
            candidates = candidates[~candidates[self._id_col].astype(str).isin(exclude_ids)]

        if candidates.empty:
            return None

        return candidates.sample(1).iloc[0].to_dict()

    # ── Batch selection (for testing / simulation) ─────────────────────────

    def select_session_questions(self, student_id: str, practice_category: str,
                                  n: int = 10) -> List[dict]:
        """Select n questions for a full practice session, scoped to one
        practice_category (see select_question)."""
        questions = []
        session_ids = []
        for _ in range(n):
            q = self.select_question(student_id, practice_category, session_ids)
            if q:
                qid = str(q.get(self._id_col, q.get("question_id")))
                session_ids.append(qid)
                questions.append(q)
        return questions

    # ── Stats ──────────────────────────────────────────────────────────────

    def get_coverage_stats(self, student_id: str, subject: str) -> dict:
        """How much of the subject's concept graph has been explored."""
        all_concepts = self.dag.get_concepts_by_subject(subject)
        mastery      = self.km.get_mastery_dict(student_id, subject)
        seen         = [c for c in all_concepts if c in mastery]
        mastered     = [c for c in seen if mastery[c] >= 0.8]

        return {
            "total_concepts":    len(all_concepts),
            "concepts_seen":     len(seen),
            "concepts_mastered": len(mastered),
            "coverage_pct":      round(len(seen) / len(all_concepts) * 100, 1) if all_concepts else 0,
            "mastery_pct":       round(len(mastered) / len(all_concepts) * 100, 1) if all_concepts else 0,
        }
