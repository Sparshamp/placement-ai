"""Paths and settings for the job-recommendation feature.

Resolved from this feature folder so they never depend on the old
research repository or a developer's absolute Windows paths.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

FEATURE_DIR = Path(__file__).resolve().parent
DATA_DIR = FEATURE_DIR / "data"
JOBS_DIR = DATA_DIR / "jobs"
PROCESSED_DIR = DATA_DIR / "processed"
RECOMMENDATIONS_DIR = DATA_DIR / "recommendations"

DEFAULT_JOBS_CSV = Path(
    os.environ.get("JOBS_CSV", str(JOBS_DIR / "all_jobs_v4.csv"))
)
JOBS_CHROMA_DIR = Path(
    os.environ.get("JOBS_CHROMA_DIR", str(DATA_DIR / "jobs_db"))
)
RESUME_CHROMA_DIR = Path(
    os.environ.get("RESUME_CHROMA_DIR", str(DATA_DIR / "chroma_db"))
)

EMBEDDING_MODEL = os.environ.get("JOB_EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
CROSS_ENCODER_MODEL = os.environ.get(
    "JOB_CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

MAX_RESUME_BYTES = int(os.environ.get("MAX_RESUME_BYTES", str(5 * 1024 * 1024)))
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx", ".txt"}

DEFAULT_TOP_K = int(os.environ.get("JOB_RECOMMEND_TOP_K", "12"))
STAGE1_N_RESULTS = int(os.environ.get("JOB_STAGE1_N_RESULTS", "1000"))
COLBERT_TOP_N = int(os.environ.get("JOB_COLBERT_TOP_N", "100"))

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

TAILORED_RESUME_MODEL = os.environ.get("TAILORED_RESUME_MODEL", OLLAMA_MODEL)
SKILL_GAP_MODEL = os.environ.get("SKILL_GAP_MODEL", OLLAMA_MODEL)