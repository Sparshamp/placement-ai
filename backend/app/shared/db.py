"""Single Postgres engine getter, shared across features that need
the relational DB (currently: auth; adaptive_aptitude has its own
copy in data/db_loader.py — safe to dedupe later, not touched here)."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

PG_HOST = os.environ.get("POSTGRES_HOST", "localhost")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
PG_USER = os.environ.get("POSTGRES_USER", "adaptive_user")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "adaptive_pass")
PG_DB = os.environ.get("POSTGRES_DB", "adaptive_aptitude")

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine