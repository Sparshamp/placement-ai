"""One-off full rebuild of the local jobs Chroma collection."""

import logging

from app.features.job_recommendation.ingest_jobs import JobIngestionEngine


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    engine = JobIngestionEngine()
    engine.load_jobs_from_csv()
    embeddings = engine.build_job_embeddings(batch_size=8)
    stored = engine.store_jobs_in_chromadb(embeddings)
    print(f"REBUILD_COMPLETE stored={stored}")
