"""ColBERT token encoder and MaxSim — production pieces used by the hybrid pipeline."""
from __future__ import annotations

import numpy as np

try:
    import torch
    from transformers import AutoModel, AutoTokenizer
except ImportError as exc:
    raise ImportError("pip install torch transformers") from exc


class ColBERTEncoder:
    MODEL_NAME = "bert-base-uncased"
    MAX_LENGTH = 180
    QUERY_MAX_LEN = 64

    def __init__(self):
        print(f"[ColBERT] Loading BERT: {self.MODEL_NAME}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        self.model = AutoModel.from_pretrained(self.MODEL_NAME)
        self.model.eval()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        print(f"[ColBERT] Device: {self.device}")

    @torch.no_grad()
    def encode(self, text: str, max_length: int = MAX_LENGTH, is_query: bool = False) -> np.ndarray:
        marker = "[unused0]" if is_query else "[unused1]"
        enc = self.tokenizer(
            f"{marker} {text}", max_length=max_length,
            truncation=True, padding=False, return_tensors="pt",
        ).to(self.device)

        out = self.model(**enc)
        vecs = out.last_hidden_state[0].cpu().numpy()
        input_ids = enc["input_ids"][0].cpu().numpy()
        mask = input_ids != self.tokenizer.pad_token_id
        vecs = vecs[mask]

        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.where(norms < 1e-9, 1.0, norms)
        return vecs / norms


def maxsim_score(query_vecs: np.ndarray, doc_vecs: np.ndarray) -> float:
    sim = np.dot(query_vecs, doc_vecs.T)
    return float(sim.max(axis=1).sum())
