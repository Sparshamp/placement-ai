"""Ingest jobs CSV into ChromaDB using BGE embeddings (same model as resume query vectors)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from app.features.job_recommendation.config import (
    DEFAULT_JOBS_CSV,
    EMBEDDING_MODEL,
    JOBS_CHROMA_DIR,
)

logger = logging.getLogger(__name__)


class JobIngestionEngine:
    def __init__(self, model_name: str = EMBEDDING_MODEL, persist_dir: Optional[str] = None):
        from sentence_transformers import SentenceTransformer
        import chromadb

        self.model_name = model_name
        self.persist_dir = persist_dir or str(JOBS_CHROMA_DIR)
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        logger.info("Loading embedding model for job ingest: %s", model_name)
        self.embedder = SentenceTransformer(model_name, device="cpu")

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="jobs",
            metadata={"hnsw:space": "cosine"},
        )
        self.jobs_df = None

    def load_jobs_from_csv(self, csv_path: Optional[str] = None) -> pd.DataFrame:
        csv_path = Path(csv_path or DEFAULT_JOBS_CSV)
        if not csv_path.exists():
            raise FileNotFoundError(f"Job CSV not found: {csv_path}")
        df = pd.read_csv(csv_path, encoding="utf-8-sig").fillna("")
        required_cols = ["Title", "Company", "Job Description", "Skills", "Domain"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        self.jobs_df = df
        logger.info("Loaded %s jobs from %s", len(df), csv_path)
        return df

    def clean_job_text(self, text: str, max_length: int = 2000) -> str:
        if not isinstance(text, str):
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", text)
        return text.strip()[:max_length]

    def ingest_pipeline(self, csv_path: Optional[str] = None, max_jobs: Optional[int] = None) -> Tuple[pd.DataFrame, Dict]:
        """Build a full index unless an explicit caller-provided test cap is used."""
        df = self.load_jobs_from_csv(csv_path)
        if max_jobs is not None:
            df = df.head(int(max_jobs)).reset_index(drop=True)
            self.jobs_df = df
            logger.info("Explicitly capped ingest to first %s jobs", len(df))

        embeddings = self.build_job_embeddings()
        stored = self.store_jobs_in_chromadb(embeddings)
        return df, {"stored": stored, "persist_dir": self.persist_dir}

    def build_job_embeddings(self, batch_size: int = 32) -> Dict[int, object]:
        import numpy as np

        embeddings: Dict[int, np.ndarray] = {}
        total = len(self.jobs_df)
        logger.info("Generating embeddings for %s jobs", total)
        for idx in range(0, total, batch_size):
            batch_end = min(idx + batch_size, total)
            batch_jobs = self.jobs_df.iloc[idx:batch_end]
            texts = []
            for _, job in batch_jobs.iterrows():
                text = f"{job['Title']} {job['Domain']} {job['Job Description']} {job['Skills']}"
                texts.append(self.clean_job_text(text))
            batch_embeddings = self.embedder.encode(texts, convert_to_numpy=True)
            for i, emb in enumerate(batch_embeddings):
                embeddings[idx + i] = emb
            logger.info("Embedded jobs %s/%s", batch_end, total)
        return embeddings

    def store_jobs_in_chromadb(self, embeddings: dict) -> int:
        ids, documents, metadatas, embeddings_list = [], [], [], []
        for idx, emb in embeddings.items():
            job = self.jobs_df.iloc[idx]
            ids.append(f"job_{idx}")
            documents.append(self.clean_job_text(f"{job['Title']} {job['Job Description']}"))
            metadatas.append({
                "title": str(job["Title"])[:500],
                "company": str(job["Company"])[:200],
                "domain": str(job["Domain"])[:100],
                "skills": str(job["Skills"])[:500],
                "experience_level": str(job.get("Experience Level", ""))[:100],
                "salary": str(job.get("Salary", ""))[:100],
                "location": str(job.get("Location", ""))[:100],
                "work_type": str(job.get("Work Type", ""))[:50],
                "source": str(job.get("Source", ""))[:50],
                "job_index": idx,
            })
            embeddings_list.append(emb.tolist() if hasattr(emb, "tolist") else list(emb))

        # Replace any previous index so job_index stays aligned with the CSV.
        existing = self.collection.count()
        if existing:
            try:
                self.client.delete_collection("jobs")
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(
                name="jobs",
                metadata={"hnsw:space": "cosine"},
            )

        BATCH_SIZE = 2000
        total = len(ids)
        for start in range(0, total, BATCH_SIZE):
            end = min(start + BATCH_SIZE, total)
            self.collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                embeddings=embeddings_list[start:end],
            )
            logger.info("Stored jobs batch %s-%s of %s", start, end, total)
        return total


def ensure_jobs_index() -> int:
    """Return the number of jobs in Chroma, ingesting from CSV if empty."""
    import chromadb

    JOBS_CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(JOBS_CHROMA_DIR))
    collection = client.get_or_create_collection(
        name="jobs",
        metadata={"hnsw:space": "cosine"},
    )
    count = collection.count()
    if count > 0:
        return count
    logger.info("Jobs collection empty — running ingest from CSV")
    engine = JobIngestionEngine()
    _, stats = engine.ingest_pipeline()
    return int(stats["stored"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    stored = ensure_jobs_index()
    print(f"Jobs index ready: {stored} jobs")
