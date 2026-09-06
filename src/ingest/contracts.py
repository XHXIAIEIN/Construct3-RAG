"""Typed contracts shared by ingest preparation and vector publication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


RESERVED_PAYLOAD_KEYS = frozenset({"document_id", "text"})


class VectorMode(str, Enum):
    """Supported Qdrant vector layouts."""

    DENSE = "dense"
    DENSE_BM25 = "dense_bm25"
    DENSE_NATIVE_SPARSE = "dense_native_sparse"

    @property
    def uses_sparse(self) -> bool:
        return self is not VectorMode.DENSE

    @property
    def uses_bm25(self) -> bool:
        return self is VectorMode.DENSE_BM25

    @classmethod
    def resolve(
        cls,
        *,
        bm25_enabled: bool,
        native_sparse_enabled: bool,
    ) -> "VectorMode":
        if native_sparse_enabled:
            return cls.DENSE_NATIVE_SPARSE
        if bm25_enabled:
            return cls.DENSE_BM25
        return cls.DENSE


@dataclass(frozen=True)
class VectorDocument:
    """Validated document passed from ingest builders to a vector adapter.

    ``document_id`` is the rebuild-stable source identity. Qdrant may use a
    backend-specific point ID, but this original identity is always retained in
    the payload.
    """

    document_id: str
    collection_name: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        document_id = str(self.document_id).strip()
        collection_name = str(self.collection_name).strip()
        if not document_id:
            raise ValueError("VectorDocument.document_id must not be empty")
        if not collection_name:
            raise ValueError("VectorDocument.collection_name must not be empty")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("VectorDocument.text must be a non-empty string")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("VectorDocument.metadata must be a mapping")

        metadata = dict(self.metadata)
        non_string_keys = [key for key in metadata if not isinstance(key, str)]
        if non_string_keys:
            raise TypeError("VectorDocument.metadata keys must be strings")
        conflicts = RESERVED_PAYLOAD_KEYS.intersection(metadata)
        if conflicts:
            names = ", ".join(sorted(conflicts))
            raise ValueError(f"VectorDocument.metadata uses reserved payload keys: {names}")
        try:
            json.dumps(metadata, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise TypeError("VectorDocument.metadata must be JSON serializable") from exc

        object.__setattr__(self, "document_id", document_id)
        object.__setattr__(self, "collection_name", collection_name)
        object.__setattr__(self, "metadata", metadata)

    @classmethod
    def from_legacy(
        cls,
        value: "VectorDocument | Mapping[str, Any]",
        *,
        collection_name: str,
    ) -> "VectorDocument":
        """Validate a historical ``{id, text, metadata}`` mapping."""
        if isinstance(value, cls):
            if value.collection_name != collection_name:
                raise ValueError(
                    "VectorDocument collection mismatch: "
                    f"{value.collection_name!r} != {collection_name!r}"
                )
            return value
        if not isinstance(value, Mapping):
            raise TypeError("documents must contain VectorDocument or mapping values")

        text = value.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("legacy vector document requires non-empty text")
        document_id = value.get("id") or value.get("document_id")
        if document_id is None or not str(document_id).strip():
            document_id = hashlib.md5(text.encode("utf-8")).hexdigest()
        metadata = value.get("metadata", {})
        return cls(
            document_id=str(document_id),
            collection_name=collection_name,
            text=text,
            metadata=metadata,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "text": self.text,
            **dict(self.metadata),
        }

    def to_legacy(self) -> dict[str, Any]:
        return {
            "id": self.document_id,
            "text": self.text,
            "metadata": dict(self.metadata),
        }


class PipelineStage(str, Enum):
    PREPARE = "prepare"
    VALIDATE = "validate"
    PUBLISH = "publish"
    VERIFY = "verify"


@dataclass(frozen=True)
class PipelineStageReport:
    stage: PipelineStage
    document_count: int
    collection_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        if self.document_count < 0:
            raise ValueError("document_count must not be negative")
        counts = {str(name): int(count) for name, count in self.collection_counts.items()}
        if any(count < 0 for count in counts.values()):
            raise ValueError("collection counts must not be negative")
        object.__setattr__(self, "collection_counts", counts)


@dataclass
class PipelineReport:
    """Ordered reports for one prepare/validate/publish/verify run."""

    rebuild: bool
    stages: list[PipelineStageReport] = field(default_factory=list)

    def add(
        self,
        stage: PipelineStage,
        collection_counts: Mapping[str, int],
    ) -> PipelineStageReport:
        report = PipelineStageReport(
            stage=stage,
            document_count=sum(collection_counts.values()),
            collection_counts=collection_counts,
        )
        self.stages.append(report)
        return report

    @property
    def completed_stages(self) -> tuple[PipelineStage, ...]:
        return tuple(report.stage for report in self.stages)


def validate_document_set(
    documents: Mapping[str, Iterable[VectorDocument]],
) -> dict[str, list[VectorDocument]]:
    """Materialize and validate collection membership and unique IDs."""
    validated: dict[str, list[VectorDocument]] = {}
    for collection_name, values in documents.items():
        rows = list(values)
        seen: set[str] = set()
        for document in rows:
            if not isinstance(document, VectorDocument):
                raise TypeError("pipeline document sets must contain VectorDocument values")
            if document.collection_name != collection_name:
                raise ValueError(
                    "VectorDocument collection mismatch: "
                    f"{document.collection_name!r} != {collection_name!r}"
                )
            if document.document_id in seen:
                raise ValueError(
                    f"duplicate document_id in {collection_name}: {document.document_id}"
                )
            seen.add(document.document_id)
        validated[collection_name] = rows
    return validated
