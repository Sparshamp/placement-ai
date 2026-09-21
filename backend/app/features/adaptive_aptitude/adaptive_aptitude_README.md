# Adaptive Aptitude Practice

Adaptive test-prep engine: picks the next-best question for a student in
real time based on their evolving mastery of ~2,539 concepts, rather than
serving questions from a fixed, linear test.

This document covers implementation details for this feature specifically.
For overall repo setup, see the root `README.md`.

## How it works

**Mastery tracking — BKT + EMA.** Each concept a student attempts is
tracked with two signals blended together: Bayesian Knowledge Tracing
(a probabilistic model of "does the student know this concept"), and an
Exponential Moving Average over recent correctness (a simpler recency-
weighted signal). The final skill score is `0.6 * bkt + 0.4 * ema` — BKT
alone reacts too slowly to a sudden slump or streak, EMA alone has no
memory of long-run performance, and the blend covers both.

**Question selection — Concept DAG + ε-greedy, concept-focused.**
Concepts aren't independent; some are prerequisites for others (~2,539
concepts, stored as a Postgres DAG). The selector policy was chosen after
running an 8-algorithm experiment harness that tested selection
strategies against ROC-AUC under two different simulators (BKT-generative
and IRT-generative): **staying focused on one concept until it's mastered
or exhausted, then advancing**, beat "roaming" across concepts on every
metric, under both simulators. That's the production policy —
`bkt_ema_epsilon_greedy_focused`. The ε-greedy part (ε=0.20) means 20% of
the time the engine deliberately picks a question outside the "optimal"
next concept, to avoid getting stuck only reinforcing what the student
already knows.

**Session scoping.** Sessions are scoped by `practice_category` — 5
broad, student-facing buckets ("Core CS", "Aptitude", "Programming & DSA",
"Engineering Mathematics", "Data Science & AI") — not by the 22 finer
`canonical_subject` labels. A student picks a `practice_category` to start
a session; `canonical_subject` is still tracked underneath for dashboard
mastery rollups, it's just not the pool boundary. This distinction matters
because cross-subject prerequisites exist (e.g. a Databases concept can
depend on a Discrete Math concept) — scoping too narrowly by subject alone
silently locks concepts whose prerequisites sit in a different subject.

## Backend structure

```
app/features/adaptive_aptitude/
├── router.py              # FastAPI endpoints (APIRouter, prefix /api/adaptive-aptitude)
├── core/
│   ├── knowledge_model.py     # BKT/EMA math, per-subject BKT param table
│   ├── knowledge_model_pg.py  # Postgres-backed student knowledge model
│   ├── concept_dag.py         # in-memory DAG structure + traversal
│   └── question_selector.py   # the ε-greedy, concept-focused selection policy
├── data/
│   ├── db_loader.py           # Postgres + MinIO connection/config
│   ├── dataset_loader.py      # legacy CSV loader (superseded by Postgres, kept for reference)
│   ├── questions_clean.json
│   └── questions_with_image.json
├── data_resolved.py       # loads the real Postgres DAG + `questions_resolved` view
└── db/
    ├── schema.sql              # base schema
    └── schema_extended.sql     # sessions/responses/mastery tables (Phase 2)
```

Storage is Postgres-backed (`PostgresStudentKnowledgeModel`), `student_sessions`, `student_responses`, and
`student_mastery` tables (see `schema_extended.sql`). `session_id` is a real Postgres UUID returned by
`start_session()` and required on every subsequent answer submission.

## API endpoints

All under `/api/adaptive-aptitude`:

| Method | Path | Purpose |
|---|---|---|
| POST | `/session/start` | Start a session scoped to one `practice_category` |
| GET | `/question/next` | Get the next best question for a student in a session |
| POST | `/question/answer` | Submit an answer → updated mastery + next question |
| GET | `/student/{id}/summary` | Full mastery dashboard, optionally filtered by subject |
| GET | `/student/{id}/skills` | Per-concept skill scores for one subject |
| GET | `/student/{id}/history` | Recent interaction log |
| GET | `/practice-categories` | The 5 session-scoping buckets |
| GET | `/subjects` | The 22 canonical subjects (reporting only) |
| GET | `/dag/{subject}` | Concept graph for one subject, for visualization |

Answer correctness is always determined server-side by `question_id` —
the client cannot supply `correct_answer` on submission, so there's no way
to spoof a score from the frontend.

## Question bank

Sourced from OCR-extracted GATE exam questions (Engineering Mathematics,
General Aptitude, Theory of Computation, Programming in C, Data Analysis),
cleaned and validated into a strict schema (all 18 canonical fields
required, `json.dumps()`-enforced valid JSON). Loaded into Postgres via
the `questions_resolved` view, which joins in `canonical_subject`,
`concept_id`, and `practice_category` so every question is
concept-DAG-aware, not just subject-tagged.

## Environment variables

Read from `backend/.env` (see root README for the full template):

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_USER=adaptive_user
POSTGRES_PASSWORD=adaptive_pass
POSTGRES_DB=adaptive_aptitude
MINIO_ENDPOINT=localhost:9000
MINIO_BUCKET=question-images
```

If Postgres/MinIO aren't reachable at startup, the router logs a warning
and serves an empty question bank rather than crashing — useful if a
teammate is running the backend only to test the interview feature.

## Frontend structure

```
frontend/src/features/adaptive-aptitude/
├── api.js                      # thin fetch client, base URL http://localhost:8001
├── Practice.jsx                 # main practice session UI
├── Dashboard.jsx                # mastery dashboard
└── components/
    ├── QuestionCard.jsx
    ├── MasteryRing.jsx / .css
    └── ReviewPanel.jsx
```

Routes: `/` (Practice), `/dashboard` (Dashboard) — both wrapped in the
shared `Layout` component for consistent navigation.

## Known trade-offs / things to know before extending

- The resume-analysis/job-matching prototype for this feature was
  intentionally excluded from this integration due to RAM constraints —
  not part of this repo.
- `dataset_loader.py` (CSV-based) is legacy; all current loading goes
  through `db_loader.py` / `data_resolved.py` against Postgres.
- BKT parameters are tuned via `sweep_bkt_params.py` (not part of the
  runtime app — a research script, kept outside `backend/`) against all
  22 canonical subjects, not sourced from any external dataset.
