"""Build a structured query string and BGE embeddings for a resume."""
import logging

from app.features.job_recommendation.config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model (%s)", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def build_query_string(entities: dict, sections: dict) -> str:
    parts = []

    if entities.get("skills"):
        parts.append("[SKILLS] " + ", ".join(entities["skills"][:20]))

    exp_parts = []
    if entities.get("years_exp"):
        exp_parts.append(entities["years_exp"])
    if entities.get("organizations"):
        exp_parts.append("at " + ", ".join(entities["organizations"][:2]))
    if exp_parts:
        parts.append("[EXP] " + " ".join(exp_parts))

    exp_text = sections.get("experience", "")
    if exp_text:
        first_line = exp_text.split("\n")[0].strip()
        if first_line:
            parts.append("[ROLE] " + first_line[:80])

    edu_text = sections.get("education", "")
    if edu_text:
        first_line = edu_text.split("\n")[0].strip()
        if first_line:
            parts.append("[EDU] " + first_line[:80])

    return "  ".join(parts)


def embed(text: str) -> list:
    if not text.strip():
        return []
    model = _get_model()
    vector = model.encode(
        f"Represent this resume for job matching: {text}",
        normalize_embeddings=True,
    )
    return vector.tolist()


def build_section_embeddings(sections: dict) -> dict:
    model = _get_model()
    result = {}
    for key in ["skills", "experience", "education", "projects"]:
        text = sections.get(key, "").strip()
        if text:
            v = model.encode(
                f"Resume {key} section: {text[:1000]}",
                normalize_embeddings=True,
            )
            result[key] = v.tolist()
        else:
            result[key] = []
    return result


def build_embeddings(entities: dict, sections: dict) -> dict:
    query_string = build_query_string(entities, sections)
    fallback = sections.get("other", "") or " ".join(
        v for v in sections.values() if v
    )[:1500]
    if not query_string.strip():
        query_string = fallback[:500]
    query_vector = embed(query_string)
    section_vectors = build_section_embeddings(sections)
    return {
        "query_string": query_string,
        "query_vector": query_vector,
        "section_vectors": section_vectors,
    }
