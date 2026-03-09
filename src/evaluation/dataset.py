from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.config import DATA_DIR


DEFAULT_DATASET_PATH = Path(DATA_DIR) / "ragas_dataset.json"


@dataclass
class EvalCase:
    id: str
    query: str
    ground_truth: str
    expected_keywords: List[str] = field(default_factory=list)
    category: str = "general"
    forbidden_phrases: List[str] = field(default_factory=list)
    has_answer: bool = True
    note: str = ""


@dataclass
class EvalDataset:
    cases: List[EvalCase]

    @classmethod
    def load(cls, path: Path = DEFAULT_DATASET_PATH) -> "EvalDataset":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        cases = [EvalCase(**item) for item in raw]
        return cls(cases=cases)

    def save(self, path: Path = DEFAULT_DATASET_PATH) -> None:
        data = [vars(c) for c in self.cases]
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, case_id: str) -> Optional[EvalCase]:
        return next((c for c in self.cases if c.id == case_id), None)

    def filter_by_category(self, category: str) -> "EvalDataset":
        return EvalDataset([c for c in self.cases if c.category == category])
