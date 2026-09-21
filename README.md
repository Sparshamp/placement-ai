# AI-Powered Placement & Career Assistant

A unified platform for placement preparation, built as a PES University
sixth-semester Capstone Project (UE23CS320B).

**Team:** Dhruthi Rajesh Kedilaya, Shreya C, Sparsha M P,  Yogitha A S
**Guide:** Dr. Ashwini M Joshi

## What's in this repo (current implementation)

Three features are integrated into one frontend + one backend so far:

| Feature | Frontend route | Backend prefix |
|---|---|---|
| Adaptive Aptitude Practice | `/` , `/practice` | `/api/adaptive-aptitude` |
| Mock Interview Simulation | `/interview` | `/api/interview-simulation` |
| Job Recommendation + tailored resume | `/jobs` | `/api/job-recommendation` |

Skill Recommendation is the remaining capstone component and is not yet wired in.

## Architecture

Both frontend and backend follow a **feature-folder** structure: each
feature owns its own code end-to-end, and only wires into one shared
entry point.

```
AI-Powered-Placement-and-Career-Assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                     # single FastAPI app — includes every feature's router
│   │   └── features/
│   │       ├── adaptive_aptitude/      # BKT + Concept DAG adaptive test engine
│   │       ├── interview_simulation/   # AI mock interview (LLM + STT + emotion)
│   │       └── job_recommendation/     # resume preprocess + hybrid matcher + tailor
│   ├── whisper_server.py               # standalone STT microservice (its own process, port 8000)
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── main.jsx / App.jsx          # single entry point, routes to all features
    │   ├── shared/                     # code used by more than one feature
    │   │   ├── api/httpClient.js
    │   │   └── components/Layout.jsx, ThemeToggle.jsx
    │   └── features/
    │       ├── adaptive-aptitude/
    │       ├── interview-simulation/
    │       └── job-recommendation/
    └── package.json
```

**Rule of thumb for contributors:** if a file is only used by your
feature, it lives inside your feature folder. If two or more features
need it (e.g. the page layout, the HTTP client), it goes in `shared/`.

## Tech stack

- **Frontend:** React 18.3.1, Vite 5.4.0, React Router 7, Axios, ESLint, Vitest
- **Backend:** FastAPI, Uvicorn, Python 3.12
- **Adaptive Aptitude:** PostgreSQL (pgvector, JSONB, recursive CTEs), MinIO
- **Interview Simulation:** Ollama (LLM, GPU-hosted), faster-whisper (STT), DeepFace + OpenCV (emotion), browser Web Speech API (TTS)
- **Job Recommendation:** spaCy + skillNer resume parsing, BGE embeddings, ChromaDB, ColBERT MaxSim, MS-MARCO cross-encoder; optional Gemini/Ollama for tailored resumes

## Ports

| Service | Port | Notes |
|---|---|---|
| Frontend (Vite dev server) | 5173 | `npm run dev` |
| Backend (FastAPI, all features) | 8001 | `uvicorn app.main:app --port 8001` |
| Whisper STT microservice | 8000 | separate process, `whisper_server.py` |
| Ollama LLM | 11434 | runs on a separate GPU machine, not local |
| PostgreSQL | 5432 | adaptive aptitude only |
| MinIO | 9000 | adaptive aptitude only, question images |

## Prerequisites

- Node.js 18+ and npm
- Python 3.12 (a virtual environment is strongly recommended)
- PostgreSQL 14+ (only required for the adaptive aptitude feature)
- MinIO (only required for adaptive aptitude question images)
- An Ollama server reachable over the network (only required for the interview feature — ask your teammate for the current GPU machine's IP)

You do **not** need Postgres/MinIO to work on the interview feature, and
you do **not** need a GPU or Ollama access to work on adaptive aptitude —
each feature's backend router only touches its own infrastructure at
request time, not at import time, with one exception noted below.

## Setup

### 1. Clone and install backend deps

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

The first job-recommendation request also downloads Hugging Face models
(`BAAI/bge-large-en-v1.5`, `bert-base-uncased`, `cross-encoder/ms-marco-MiniLM-L-6-v2`)
if they are not already cached.

Optional, once, to pre-build the jobs Chroma index (otherwise it is built on
the first recommendation request):

```bash
# From backend/, with env vars loaded. JOB_INGEST_MAX caps CSV rows for a faster first run.
set JOB_INGEST_MAX=200
python -m app.features.job_recommendation.ingest_jobs
```

> **Heads up:** `app/main.py` imports both features' routers unconditionally
> at startup, and the interview feature's emotion analyzer imports
> `deepface`/`opencv`/`tf-keras` at the top of its file. This means the
> **whole `requirements.txt` must be installed for the app to start at all**,
> even if you're only working on one feature. These libraries don't need a
> GPU to import — only to run — so this works fine on a CPU machine, just
> expect a slower first import while TensorFlow loads.

### 2. Backend environment variables

Create `backend/.env` (gitignored — not committed, every developer creates their own):

```env
# PostgreSQL — adaptive aptitude
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=adaptive_user
POSTGRES_PASSWORD=adaptive_pass
POSTGRES_DB=adaptive_aptitude

# MinIO — adaptive aptitude question images
MINIO_ENDPOINT=localhost:9000
MINIO_BUCKET=question-images

# Job recommendation (optional)
GEMINI_API_KEY=
JOB_INGEST_MAX=200
```

If you're only working on the interview feature and don't have Postgres/MinIO
running locally, that's fine — the adaptive aptitude router catches the
connection failure at startup and serves an empty question bank instead of
crashing the whole app.

### 3. Frontend environment variables

Create `frontend/.env` (gitignored):

```env
VITE_API_BASE_URL=http://localhost:8001
```

This is required for **all** features.

### 4. Install frontend deps

```bash
cd frontend
npm install
```

## Running the app

Three terminals, in this order:

```bash
# Terminal 1 — Whisper STT microservice (only needed to test the interview feature)
cd backend
uvicorn whisper_server:app --port 8000

# Terminal 2 — main API (all features)
cd backend
uvicorn app.main:app --port 8001 --reload

# Terminal 3 — frontend
cd frontend
npm run dev
```

Then open `http://localhost:5173`.

- `/` and `/practice` — adaptive aptitude practice
- `/interview` — mock interview simulation (needs Terminal 1 running, plus Ollama reachable at the GPU IP set in `backend/app/features/interview_simulation/config.py`)
- `/jobs` — job recommendations and tailored resumes (needs the jobs CSV under `backend/app/features/job_recommendation/data/jobs/`, plus a Chroma jobs index)

## Known limitations / in progress

- Interview simulation requires a GPU machine running Ollama; not
  available on CPU-only setups without that remote connection.
- Job recommendation loads embedding/ColBERT/cross-encoder models on the
  first request; that can take several minutes on CPU.
- Skill-gap analysis is not yet wired into this repo.
- Linked assets in `frontend/src/assets/` (`hero.png`, `react.svg`, etc.)
  are leftover Vite boilerplate and can be cleaned up once `App.jsx` no
  longer references them.

See `backend/app/features/adaptive_aptitude/README.md` for implementation
details on the adaptive testing engine specifically.
