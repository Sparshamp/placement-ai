"""Cross-encoder reranker and condensed-resume builder used by the hybrid pipeline."""
from __future__ import annotations

from typing import List, Optional

import numpy as np

try:
    from sentence_transformers import CrossEncoder
except ImportError as exc:
    raise ImportError("pip install sentence-transformers") from exc


def build_condensed_resume(preprocessed: dict, max_chars: int = 700) -> str:
    sections = preprocessed.get("sections", {})
    query_string = preprocessed["embeddings"].get("query_string", "")

    parts = []
    budget = max_chars

    if query_string and budget > 0:
        chunk = query_string[:budget]
        parts.append(chunk)
        budget -= len(chunk)

    for key in ["summary", "skills", "experience"]:
        text = sections.get(key, "").strip()
        if text and budget > 50:
            chunk = text[:budget]
            parts.append(chunk)
            budget -= len(chunk)

    return "\n".join(parts) if parts else query_string


class CrossEncoderReranker:
    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or self.MODEL_NAME
        print(f"[CrossEncoder] Loading: {self.model_name}")
        self.model = CrossEncoder(self.model_name, max_length=512)

    def score_pairs(self, query: str, passages: List[str], batch_size: int = 32) -> np.ndarray:
        pairs = [(query, p) for p in passages]
        raw_scores = self.model.predict(pairs, batch_size=batch_size, show_progress_bar=False)
        return 1.0 / (1.0 + np.exp(-np.array(raw_scores)))
