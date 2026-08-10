"""Independent stage-two semantic retrieval evaluation support.

The package deliberately keeps live Qdrant/model imports behind the CLI path so
the unit-test suite remains offline and does not load embedding models.
"""

from .core import (
    Candidate,
    CandidateBatch,
    CollectionBatch,
    EvaluationConfig,
    EvaluationRunner,
)
from .models import FixtureError, GoldCase, load_fixture
from .stable_ids import StableIdError, stable_result_id

__all__ = [
    "Candidate",
    "CandidateBatch",
    "CollectionBatch",
    "EvaluationConfig",
    "EvaluationRunner",
    "FixtureError",
    "GoldCase",
    "StableIdError",
    "load_fixture",
    "stable_result_id",
]
