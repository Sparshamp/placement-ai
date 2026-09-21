"""Run resume preprocessing steps 1–4 for a single uploaded resume."""
from .step1_parser import parse_resume_bytes
from .step2_segmentation import segment_resume
from .step3_ner import extract_all_entities
from .step4_embeddings import build_embeddings


def process_one(parsed: dict) -> dict:
    raw = parsed["raw_text"]
    secs = segment_resume(raw)
    ents = extract_all_entities(raw, secs)
    embs = build_embeddings(ents, secs)
    return {
        "filename": parsed["filename"],
        "file_type": parsed["file_type"],
        "raw_text": raw,
        "sections": secs,
        "entities": ents,
        "embeddings": embs,
    }
