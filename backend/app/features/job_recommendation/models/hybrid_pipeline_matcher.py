"""
hybrid_pipeline_matcher.py
---------------------------
Four-stage staged pipeline (adapted from the research repo for FastAPI):

    Stage 1 -- Dense Bi-Encoder Retrieval (ChromaDB, precomputed query_vector)
    Stage 2 -- Skill-Level ColBERT MaxSim reranking/filtering
    Stage 3 -- Experience Compatibility filtering
    Stage 4 -- Cross-Encoder reranking (primary final signal)
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.features.job_recommendation.config import (
    COLBERT_TOP_N,
    CROSS_ENCODER_MODEL,
    DEFAULT_JOBS_CSV,
    JOBS_CHROMA_DIR,
    STAGE1_N_RESULTS,
)
from app.features.job_recommendation.models.base_matcher import BaseMatcher
from app.features.job_recommendation.models.colbert_encoder import ColBERTEncoder, maxsim_score
from app.features.job_recommendation.models.cross_encoder import (
    CrossEncoderReranker,
    build_condensed_resume,
)

logger = logging.getLogger(__name__)

try:
    import chromadb
except ImportError as exc:
    raise ImportError("pip install chromadb") from exc


def _safe_job_index(metadata: dict) -> int:
    j = metadata.get("job_index", -1)
    try:
        v = int(j)
        return v if v >= 0 else -1
    except (TypeError, ValueError):
        return -1


def _split_skills(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"[,;/\n]+", str(text))
    return [p.strip(" -:.") for p in parts if p.strip(" -:.")]


EXPERIENCE_LEVEL_ORDER = {
    "Entry Level": 0,
    "Junior (1-3 yrs)": 1,
    "Mid Level (3-5 yrs)": 2,
    "Senior (5+ yrs)": 3,
    "Lead/Principal (8+ yrs)": 4,
}


def _parse_resume_years(years_exp_text: str) -> Optional[float]:
    if not years_exp_text:
        return None
    match = re.match(r"(\d+(?:\.\d+)?)", str(years_exp_text).strip())
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _resume_level_from_years(years: Optional[float]) -> Optional[str]:
    if years is None:
        return None
    if years < 1:
        return "Entry Level"
    if years < 3:
        return "Junior (1-3 yrs)"
    if years < 5:
        return "Mid Level (3-5 yrs)"
    if years < 8:
        return "Senior (5+ yrs)"
    return "Lead/Principal (8+ yrs)"


def compute_experience_compatibility(
    resume_years: Optional[float],
    job_level_text: str,
    tolerance: int = 1,
) -> Dict:
    job_level_raw = (job_level_text or "").strip()
    job_level = job_level_raw if job_level_raw in EXPERIENCE_LEVEL_ORDER else None

    if job_level is None:
        return {
            "compatible": True,
            "score": 1.0,
            "reason": "Job experience requirement unspecified — not filtered",
            "resume_level": _resume_level_from_years(resume_years),
            "job_level": None,
        }

    resume_level = _resume_level_from_years(resume_years)
    if resume_level is None:
        return {
            "compatible": True,
            "score": 0.5,
            "reason": "Resume years of experience unavailable — not filtered",
            "resume_level": None,
            "job_level": job_level,
        }

    diff = EXPERIENCE_LEVEL_ORDER[resume_level] - EXPERIENCE_LEVEL_ORDER[job_level]
    compatible = diff >= -tolerance
    shortfall = max(0, -diff)
    score = max(0.0, 1.0 - shortfall * 0.25)

    if diff >= 0:
        reason = f"Resume level '{resume_level}' meets or exceeds job level '{job_level}'"
    elif compatible:
        reason = (
            f"Resume level '{resume_level}' is below job level '{job_level}' "
            f"but within tolerance ({tolerance})"
        )
    else:
        reason = (
            f"Resume level '{resume_level}' is below job level '{job_level}' "
            f"beyond tolerance ({tolerance}) — filtered out"
        )

    return {
        "compatible": compatible,
        "score": round(score, 4),
        "reason": reason,
        "resume_level": resume_level,
        "job_level": job_level,
    }


class HybridPipelineEngine(BaseMatcher):
    MODEL_NAME = "HybridPipeline"

    def __init__(
        self,
        jobs_db_dir: Optional[str] = None,
        jobs_csv: Optional[str] = None,
        cross_encoder_model: Optional[str] = None,
        ce_batch_size: int = 32,
        experience_tolerance: int = 1,
    ):
        super().__init__(jobs_db_dir=jobs_db_dir, jobs_csv=jobs_csv)

        self.jobs_db_dir = jobs_db_dir or str(JOBS_CHROMA_DIR)
        self.jobs_csv = jobs_csv or str(DEFAULT_JOBS_CSV)
        self.experience_tolerance = experience_tolerance
        self.ce_batch_size = ce_batch_size

        try:
            self.chroma_client = chromadb.PersistentClient(path=self.jobs_db_dir)
            self.collection = self.chroma_client.get_or_create_collection(
                name="jobs",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Loaded jobs collection (%s jobs)", self.collection.count())
        except Exception as e:
            logger.warning("Could not load jobs ChromaDB: %s", e)
            self.collection = None

        self.jobs_df = self._load_jobs_df()
        logger.info("Loaded %s jobs metadata", len(self.jobs_df))

        self.col_encoder = ColBERTEncoder()
        self._job_skill_token_cache: Dict[int, Optional[np.ndarray]] = {}
        self.ce_reranker = CrossEncoderReranker(
            model_name=cross_encoder_model or CROSS_ENCODER_MODEL
        )
        logger.info("HybridPipeline engine ready")

    def _load_jobs_df(self) -> pd.DataFrame:
        from pathlib import Path

        p = Path(self.jobs_csv)
        return pd.read_csv(p, encoding="utf-8-sig").fillna("") if p.exists() else pd.DataFrame()

    def _job_skills_text(self, metadata: dict, job_idx: int) -> str:
        skills_text = metadata.get("skills", "")
        if (not skills_text or skills_text == "Not Listed") and 0 <= job_idx < len(self.jobs_df):
            skills_text = str(self.jobs_df.iloc[job_idx].get("Skills", ""))
        if skills_text == "Not Listed":
            skills_text = ""
        return skills_text

    def _get_job_skill_tokens(self, metadata: dict, job_idx: int) -> Optional[np.ndarray]:
        if job_idx in self._job_skill_token_cache:
            return self._job_skill_token_cache[job_idx]

        skills_text = self._job_skills_text(metadata, job_idx)
        if not skills_text.strip():
            self._job_skill_token_cache[job_idx] = None
            return None

        try:
            vecs = self.col_encoder.encode(skills_text, max_length=64, is_query=False)
        except Exception as e:
            logger.warning("skill encode failed for job %s: %s", job_idx, e)
            vecs = None

        self._job_skill_token_cache[job_idx] = vecs
        return vecs

    def _build_job_text_for_ce(self, metadata: dict, job_idx: int) -> str:
        title = metadata.get("title", "")
        company = metadata.get("company", "")
        domain = metadata.get("domain", "")
        skills = metadata.get("skills", "")
        level = metadata.get("experience_level", "")

        header = f"Job: {title}. Company: {company}. Domain: {domain}. "
        if level:
            header += f"Level: {level}. "
        if skills:
            header += f"Skills: {skills[:200]}. "

        raw_desc = ""
        if 0 <= job_idx < len(self.jobs_df):
            raw_desc = str(self.jobs_df.iloc[job_idx].get("Job Description", ""))[:400]

        return (header + raw_desc)[:700]

    def recommend(
        self,
        preprocessed: dict,
        top_k: int = 20,
        stage1_n_results: int = STAGE1_N_RESULTS,
        colbert_top_n: int = COLBERT_TOP_N,
        experience_tolerance: Optional[int] = None,
        final_score_weights: Optional[Dict[str, float]] = None,
        **kwargs,
    ) -> List[Dict]:
        if not self.validate_preprocessed(preprocessed):
            return []

        tolerance = experience_tolerance if experience_tolerance is not None else self.experience_tolerance
        entities = preprocessed.get("entities", {})
        sections = preprocessed.get("sections", {})

        if not self.collection:
            logger.error("No jobs collection loaded")
            return []

        resume_vec = np.array(preprocessed["embeddings"]["query_vector"])
        if resume_vec.size == 0:
            logger.error("Empty resume query vector")
            return []

        n_recall = min(int(stage1_n_results), 1000)
        available = self.collection.count()
        if available == 0:
            logger.error("Jobs collection is empty")
            return []
        n_recall = min(n_recall, available)

        results = self.collection.query(
            query_embeddings=[resume_vec.tolist()],
            n_results=n_recall,
            include=["documents", "metadatas", "distances"],
        )

        if not results or not results["metadatas"] or not results["metadatas"][0]:
            logger.error("No results from ChromaDB")
            return []

        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        candidates = []
        for metadata, distance in zip(metadatas, distances):
            job_idx = _safe_job_index(metadata)
            candidates.append({
                "metadata": metadata,
                "job_idx": job_idx,
                "dense_score": round(1.0 - distance, 4),
            })

        logger.info("Stage 1 (Dense Retrieval): %s candidates", len(candidates))

        resume_skills = list(entities.get("skills") or [])
        if not resume_skills:
            resume_skills = _split_skills(sections.get("skills", ""))
        resume_skills_text = ", ".join(resume_skills)

        resume_skill_tokens = None
        if resume_skills_text.strip():
            try:
                resume_skill_tokens = self.col_encoder.encode(
                    resume_skills_text, max_length=48, is_query=True
                )
            except Exception as e:
                logger.warning("resume skill encode failed: %s", e)
                resume_skill_tokens = None

        for cand in candidates:
            metadata = cand["metadata"]
            job_idx = cand["job_idx"]

            if resume_skill_tokens is None:
                cand["colbert_skill_score"] = None
                cand["_stage2_sort_key"] = cand["dense_score"]
                continue

            job_skill_tokens = self._get_job_skill_tokens(metadata, job_idx)
            if job_skill_tokens is None or len(job_skill_tokens) == 0:
                cand["colbert_skill_score"] = None
                cand["_stage2_sort_key"] = cand["dense_score"]
                continue

            raw = maxsim_score(resume_skill_tokens, job_skill_tokens)
            skill_score = raw / max(len(resume_skill_tokens), 1)
            cand["colbert_skill_score"] = round(float(skill_score), 4)
            cand["_stage2_sort_key"] = skill_score

        candidates.sort(key=lambda c: c["_stage2_sort_key"], reverse=True)
        kept_n = min(int(colbert_top_n), len(candidates))
        candidates = candidates[:kept_n]
        logger.info("Stage 2 (Skill ColBERT): kept top %s candidates", len(candidates))

        resume_years = _parse_resume_years(entities.get("years_exp", ""))
        survivors = []
        removed_count = 0
        for cand in candidates:
            metadata = cand["metadata"]
            job_level_text = metadata.get("experience_level", "")
            compat = compute_experience_compatibility(resume_years, job_level_text, tolerance=tolerance)
            cand["experience_compatibility"] = compat["score"]
            cand["experience_compatible"] = compat["compatible"]
            cand["experience_reason"] = compat["reason"]
            if compat["compatible"]:
                survivors.append(cand)
            else:
                removed_count += 1

        if not survivors:
            logger.warning("Experience filtering removed all candidates — falling back")
            survivors = candidates

        logger.info("Stage 3 (Experience Filter): removed %s, %s survive", removed_count, len(survivors))

        condensed_resume = build_condensed_resume(preprocessed)
        job_texts = [
            self._build_job_text_for_ce(cand["metadata"], cand["job_idx"])
            for cand in survivors
        ]

        if job_texts:
            ce_scores = self.ce_reranker.score_pairs(
                condensed_resume, job_texts, batch_size=self.ce_batch_size
            )
        else:
            ce_scores = []

        final_candidates = []
        for cand, ce_score in zip(survivors, ce_scores):
            metadata = cand["metadata"]
            job_idx = cand["job_idx"]

            dense_score = cand["dense_score"]
            colbert_skill_score = cand.get("colbert_skill_score")
            experience_compatibility = cand.get("experience_compatibility")
            crossencoder_score = round(float(ce_score), 4)

            if final_score_weights:
                w = final_score_weights
                parts, weight_sum = [], 0.0
                for key, val in (
                    ("dense", dense_score),
                    ("colbert_skill", colbert_skill_score),
                    ("experience_compatibility", experience_compatibility),
                    ("crossencoder", crossencoder_score),
                ):
                    weight = w.get(key)
                    if weight and val is not None:
                        parts.append(weight * val)
                        weight_sum += weight
                final_score = sum(parts) / weight_sum if weight_sum > 0 else crossencoder_score
            else:
                final_score = crossencoder_score

            desc = ""
            if 0 <= job_idx < len(self.jobs_df):
                desc = str(self.jobs_df.iloc[job_idx].get("Job Description", ""))

            final_candidates.append({
                "raw_score": final_score,
                "score": round(final_score, 4),
                "job_index": job_idx,
                "title": metadata.get("title", ""),
                "company": metadata.get("company", ""),
                "domain": metadata.get("domain", ""),
                "skills": metadata.get("skills", ""),
                "experience_level": metadata.get("experience_level", ""),
                "location": metadata.get("location", ""),
                "work_type": metadata.get("work_type", ""),
                "salary": metadata.get("salary", ""),
                "source": metadata.get("source", ""),
                "description": desc,
            })

        final_candidates.sort(key=lambda x: x["raw_score"], reverse=True)
        final = []
        for rank, r in enumerate(final_candidates[:top_k], 1):
            r_copy = dict(r)
            r_copy.pop("raw_score", None)
            r_copy["rank"] = rank
            final.append(r_copy)

        logger.info("Stage 4 (CrossEncoder): final ranking of %s recommendations", len(final))
        return final
