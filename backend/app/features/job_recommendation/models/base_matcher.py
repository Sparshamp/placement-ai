"""Unified matcher interface used by HybridPipelineEngine."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import pandas as pd


class BaseMatcher(ABC):
    MODEL_NAME = "BaseMatcher"

    def __init__(self, jobs_db_dir: Optional[str] = None,
                 jobs_csv: Optional[str] = None, **kwargs):
        self.jobs_db_dir = jobs_db_dir
        self.jobs_csv = jobs_csv
        self._load_jobs_if_available()

    def _load_jobs_if_available(self):
        self.jobs_df = None
        if self.jobs_csv:
            try:
                self.jobs_df = pd.read_csv(self.jobs_csv)
            except Exception as e:
                print(f"[{self.MODEL_NAME}] Warning: Could not load jobs CSV: {e}")

    @abstractmethod
    def recommend(self, preprocessed: dict, top_k: int = 20, **kwargs) -> List[Dict]:
        raise NotImplementedError

    def validate_preprocessed(self, preprocessed: dict) -> bool:
        required_keys = {
            "filename", "file_type", "raw_text",
            "sections", "entities", "embeddings",
        }
        if not all(k in preprocessed for k in required_keys):
            print(f"[{self.MODEL_NAME}] Error: Missing required keys in preprocessed dict")
            return False
        if "query_vector" not in preprocessed.get("embeddings", {}):
            print(f"[{self.MODEL_NAME}] Error: No query_vector in embeddings")
            return False
        return True
