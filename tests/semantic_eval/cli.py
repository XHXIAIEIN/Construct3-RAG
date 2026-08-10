"""Command-line orchestration for the real stage-two semantic benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .core import STRATEGIES, EvaluationConfig, EvaluationRunner
from .live import (
    LiveCrossEncoder,
    LiveDenseEncoder,
    LiveLookupProbe,
    LiveQdrantBackend,
    LiveSparseEncoder,
    resource_snapshot,
    runtime_identity,
)
from .metrics import paired_comparisons, stratified_summaries
from .models import (
    KNOWN_COLLECTION_KEYS,
    FixtureError,
    GoldCase,
    load_fixture,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE_DIR = ROOT / ".cache" / "query-quality" / "stage-two"
LOCKED_BEFORE_DEV = "locked_before_dev"
HELDOUT_OPEN = "dev_parameters_locked_heldout_open"
_LOCKED_STATUSES = frozenset({LOCKED_BEFORE_DEV, HELDOUT_OPEN})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_COLLECTION_NAMES = frozenset(
    f"c3_{collection}" for collection in KNOWN_COLLECTION_KEYS
)


class CliError(RuntimeError):
    pass


def _section(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    value = manifest.get(name)
    if not isinstance(value, dict):
        raise CliError(f"locked manifest requires an object at {name}")
    return value


def _required(mapping: dict[str, Any], key: str, label: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise CliError(f"locked manifest requires {label}.{key}")
    value = mapping[key]
    if isinstance(value, str) and not value.strip():
        raise CliError(f"locked manifest requires non-empty {label}.{key}")
    return value


def _required_sha256(mapping: dict[str, Any], key: str, label: str) -> str:
    value = str(_required(mapping, key, label)).casefold()
    if not _SHA256_RE.fullmatch(value):
        raise CliError(f"locked manifest {label}.{key} must be a lowercase SHA-256")
    return value


def _required_collection_list(
    comparison: dict[str, Any], key: str
) -> list[str]:
    value = _required(comparison, key, "comparison")
    if not isinstance(value, list) or not value:
        raise CliError(f"locked manifest comparison.{key} must be a non-empty array")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise CliError(f"locked manifest comparison.{key} must contain strings")
    normalized = [item.strip().casefold() for item in value]
    if len(set(normalized)) != len(normalized):
        raise CliError(f"locked manifest comparison.{key} must not contain duplicates")
    unknown = set(normalized) - KNOWN_COLLECTION_KEYS
    if unknown:
        raise CliError(
            f"locked manifest comparison.{key} has unknown collections: "
            f"{', '.join(sorted(unknown))}"
        )
    return normalized


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_directory_identity(path: Path) -> dict[str, Any]:
    """Hash a local model snapshot with the protocol's deterministic algorithm."""

    if not path.is_dir():
        raise CliError(f"model artifact directory does not exist: {path}")
    started = time.perf_counter()
    rows: list[str] = []
    file_hashes: dict[str, str] = {}
    total_bytes = 0
    files = sorted(
        (
            item
            for item in path.rglob("*")
            if item.is_file()
            and not ({".cache", "blobs", "locks"} & set(item.relative_to(path).parts))
        ),
        key=lambda item: item.relative_to(path).as_posix(),
    )
    for file_path in files:
        relative = file_path.relative_to(path).as_posix()
        size = file_path.stat().st_size
        file_sha = _sha256(file_path)
        total_bytes += size
        file_hashes[relative] = file_sha
        rows.append(f"{relative}\t{size}\t{file_sha}\n")
    digest = hashlib.sha256("".join(rows).encode("utf-8")).hexdigest()
    return {
        "path": str(path.resolve()),
        "file_count": len(files),
        "bytes": total_bytes,
        "manifest_algorithm": (
            "relative_posix_path<TAB>size<TAB>sha256(file)<LF>, sorted; "
            "exclude .cache, blobs, locks path components"
        ),
        "manifest_sha256": digest,
        "hash_elapsed_ms": (time.perf_counter() - started) * 1000,
        "file_sha256": file_hashes,
    }


def _schema_directory_identity(path: Path) -> dict[str, Any]:
    """Hash the canonical r495 tree, excluding only its export marker."""

    if not path.is_dir():
        raise CliError(f"schema directory does not exist: {path}")
    started = time.perf_counter()
    rows: list[str] = []
    total_bytes = 0
    files = sorted(
        (
            item
            for item in path.rglob("*")
            if item.is_file()
            and not (item.name == ".exported" and item.stat().st_size == 4)
        ),
        key=lambda item: item.relative_to(path).as_posix(),
    )
    for file_path in files:
        relative = file_path.relative_to(path).as_posix()
        size = file_path.stat().st_size
        total_bytes += size
        rows.append(f"{relative}\t{size}\t{_sha256(file_path)}\n")
    return {
        "path": str(path.resolve()),
        "file_count": len(files),
        "bytes": total_bytes,
        "manifest_algorithm": (
            "relative_posix_path<TAB>size<TAB>sha256(file)<LF>, sorted; "
            "exclude only 4-byte .exported marker files"
        ),
        "manifest_sha256": hashlib.sha256("".join(rows).encode("utf-8")).hexdigest(),
        "hash_elapsed_ms": (time.perf_counter() - started) * 1000,
    }


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise CliError(f"protocol manifest does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"cannot read protocol manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CliError("protocol manifest root must be an object")
    return value, _sha256(path)


def _csv(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    if not items:
        raise CliError("collection list must not be empty")
    return items


def _choose(name: str, cli_value: Any, frozen_value: Any, default: Any) -> Any:
    if frozen_value is not None:
        if cli_value is not None and cli_value != frozen_value:
            raise CliError(
                f"CLI {name}={cli_value!r} conflicts with frozen manifest value {frozen_value!r}"
            )
        return frozen_value
    return cli_value if cli_value is not None else default


def _read_locked_evidence(path_value: Any, expected_sha: str, label: str) -> dict[str, Any]:
    path = _resolved_path(str(path_value))
    if not path.is_file():
        raise CliError(f"heldout evidence {label} does not exist: {path}")
    if _sha256(path) != expected_sha:
        raise CliError(f"heldout evidence {label} SHA-256 does not match the lock")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"cannot read heldout evidence {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise CliError(f"heldout evidence {label} root must be an object")
    return {"path": str(path.resolve()), "sha256": expected_sha, "value": value}


def _validate_heldout_evidence(
    manifest: dict[str, Any], comparison: dict[str, Any]
) -> dict[str, Any]:
    required = (
        "dev_report_path",
        "dev_report_sha256",
        "dev_protocol_sha256",
        "dev_decision_path",
        "dev_decision_sha256",
        "dev_product_decision",
    )
    for key in required:
        _required(comparison, key, "comparison")
    report_sha = _required_sha256(comparison, "dev_report_sha256", "comparison")
    protocol_sha = _required_sha256(comparison, "dev_protocol_sha256", "comparison")
    decision_sha = _required_sha256(comparison, "dev_decision_sha256", "comparison")
    product_decision = str(comparison["dev_product_decision"]).strip()

    report_evidence = _read_locked_evidence(
        comparison["dev_report_path"], report_sha, "dev report"
    )
    report = report_evidence["value"]
    if report.get("status") != "complete":
        raise CliError("heldout dev report must have status=complete")
    if report.get("run", {}).get("split") != "dev":
        raise CliError("heldout dev report must contain only the dev split")
    if report.get("run", {}).get("strategies") != list(STRATEGIES):
        raise CliError("heldout dev report must contain all four frozen strategies")
    if report.get("fixture", {}).get("sha256") != comparison["semantic_gold_sha256"]:
        raise CliError("heldout dev report fixture SHA-256 does not match semantic gold")
    if report.get("protocol", {}).get("sha256") != protocol_sha:
        raise CliError("heldout dev report protocol SHA-256 does not match the lock")
    protocol_path = Path(str(report.get("protocol", {}).get("path", "")))
    if not protocol_path.is_file() or _sha256(protocol_path) != protocol_sha:
        raise CliError("the exact locked-before-dev protocol file is not preserved")
    if report.get("index_validation", {}).get("passes") is not True:
        raise CliError("heldout dev report did not pass frozen index validation")
    if not report.get("queries") or any(
        row.get("case", {}).get("split") != "dev" for row in report["queries"]
    ):
        raise CliError("heldout dev report query rows are empty or contain non-dev cases")
    configuration = report.get("configuration")
    expected_configuration = {
        "strategies": list(STRATEGIES),
        "candidate_budget_per_collection": comparison["candidate_budget_per_collection"],
        "final_top_k": comparison["final_top_k"],
        "reranker_top_k": comparison["reranker_top_k"],
        "limited_collections": comparison["limited_collections"],
        "fanout_collections": comparison["fanout_collections"],
        "weights": comparison["cross_collection_rrf_weights"],
        "rrf_base_k": comparison["rrf_base_k"],
        "adaptive_threshold": False,
        "diversity_injection": False,
        "bm25_enabled": True,
    }
    if not isinstance(configuration, dict) or any(
        configuration.get(key) != value for key, value in expected_configuration.items()
    ):
        raise CliError("heldout dev report configuration differs from frozen parameters")
    paired = report.get("paired", {})
    for key in ("fanout_vs_limited", "rrf_vs_fanout", "rerank_vs_rrf"):
        if key not in paired:
            raise CliError(f"heldout dev report is missing paired comparison {key}")
    if any(
        paired[key].get("candidate_batch_digest_all_equal") is not True
        for key in ("rrf_vs_fanout", "rerank_vs_rrf")
    ):
        raise CliError("heldout dev report did not share fanout/RRF/rerank candidates")

    decision_evidence = _read_locked_evidence(
        comparison["dev_decision_path"], decision_sha, "dev decision"
    )
    decision = decision_evidence["value"]
    if decision.get("status") != "locked_before_heldout":
        raise CliError("dev decision status must be locked_before_heldout")
    if decision.get("dev_report_sha256") != report_sha:
        raise CliError("dev decision does not bind the frozen dev report")
    if decision.get("dev_protocol_sha256") != protocol_sha:
        raise CliError("dev decision does not bind the locked-before-dev protocol")
    if decision.get("parameters_changed_after_dev") is not False:
        raise CliError("dev decision must record parameters_changed_after_dev=false")
    if decision.get("dev_product_decision") != product_decision:
        raise CliError("dev decision product decision differs from the open manifest")
    boundary = decision.get("product_boundary")
    if not isinstance(boundary, dict) or not (
        boundary.get("default_lite_mode") is True
        and boundary.get("direct_lookup_remains_default") is True
        and boundary.get("full_semantic_is_explicit_opt_in") is True
    ):
        raise CliError("dev decision does not preserve the LITE/Direct Lookup boundary")
    return {
        "dev_report": {key: report_evidence[key] for key in ("path", "sha256")},
        "dev_protocol": {"path": str(protocol_path.resolve()), "sha256": protocol_sha},
        "dev_decision": {key: decision_evidence[key] for key in ("path", "sha256")},
        "dev_product_decision": product_decision,
    }


def _lock_validation(
    manifest: dict[str, Any], fixture_sha256: str, split: str
) -> dict[str, Any]:
    comparison = _section(manifest, "comparison")
    qdrant = _section(manifest, "qdrant")
    embedding = _section(manifest, "embedding")
    reranker = _section(manifest, "reranker")
    index = _section(manifest, "index")
    schema = _section(manifest, "schema")
    heldout_gate = _section(manifest, "heldout_gate")
    product_boundary = _section(manifest, "product_boundary")

    status = str(_required(manifest, "status", "manifest"))
    if status not in _LOCKED_STATUSES:
        raise CliError(
            "locked manifest status must be exactly locked_before_dev or "
            "dev_parameters_locked_heldout_open"
        )

    frozen_hash = _required_sha256(comparison, "semantic_gold_sha256", "comparison")
    if frozen_hash != fixture_sha256:
        raise CliError("locked manifest semantic_gold_sha256 does not match the fixture")
    strategies = _required(comparison, "strategies", "comparison")
    if strategies != list(STRATEGIES):
        raise CliError(
            f"locked manifest comparison.strategies must be {list(STRATEGIES)!r}"
        )
    limited = _required_collection_list(comparison, "limited_collections")
    fanout = _required_collection_list(comparison, "fanout_collections")
    for key, expected in (
        ("candidate_budget_per_collection", 10),
        ("final_top_k", 10),
        ("reranker_top_k", 20),
        ("rrf_base_k", 60),
    ):
        value = _required(comparison, key, "comparison")
        if isinstance(value, bool) or not isinstance(value, int) or value != expected:
            raise CliError(f"locked manifest comparison.{key} must be exactly {expected}")
    if _required(comparison, "adaptive_threshold", "comparison") is not False:
        raise CliError("locked manifest comparison.adaptive_threshold must be false")
    if _required(comparison, "diversity_injection", "comparison") is not False:
        raise CliError("locked manifest comparison.diversity_injection must be false")
    weights = _required(comparison, "cross_collection_rrf_weights", "comparison")
    if not isinstance(weights, dict) or set(weights) != set(fanout):
        raise CliError(
            "locked manifest cross_collection_rrf_weights must have exactly the "
            "fanout collection keys"
        )
    for key, value in weights.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value <= 0
        ):
            raise CliError(f"locked manifest RRF weight for {key} must be positive")

    # These fields bind every quality-affecting runtime input.  The CLI may
    # repeat them for convenience, but never supply a missing frozen value.
    for key in (
        "host",
        "port",
        "timeout_seconds",
        "server_version",
        "server_commit",
        "image_digest",
    ):
        _required(qdrant, key, "qdrant")
    if (
        isinstance(qdrant["port"], bool)
        or not isinstance(qdrant["port"], int)
        or not 1 <= qdrant["port"] <= 65535
    ):
        raise CliError("locked manifest qdrant.port must be a valid TCP port")
    if (
        isinstance(qdrant["timeout_seconds"], bool)
        or not isinstance(qdrant["timeout_seconds"], (int, float))
        or not math.isfinite(float(qdrant["timeout_seconds"]))
        or qdrant["timeout_seconds"] <= 0
    ):
        raise CliError("locked manifest qdrant.timeout_seconds must be positive")
    if not re.fullmatch(r"[0-9a-f]{40}", str(qdrant["server_commit"])):
        raise CliError("locked manifest qdrant.server_commit must be a 40-hex commit")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(qdrant["image_digest"])):
        raise CliError("locked manifest qdrant.image_digest must be a sha256 digest")
    for key in (
        "model",
        "device",
        "dimension",
        "distance",
        "explicit_normalization",
        "artifact_file_count",
        "artifact_bytes",
        "model_safetensors_sha256",
        "model_manifest_sha256",
    ):
        _required(embedding, key, "embedding")
    _required_sha256(embedding, "model_safetensors_sha256", "embedding")
    _required_sha256(embedding, "model_manifest_sha256", "embedding")
    if (
        isinstance(embedding["dimension"], bool)
        or not isinstance(embedding["dimension"], int)
        or embedding["dimension"] < 1
    ):
        raise CliError("locked manifest embedding.dimension must be positive")
    if embedding["device"] not in {"cuda", "cpu"}:
        raise CliError("locked manifest embedding.device must be cuda or cpu")
    if str(embedding["distance"]).casefold() != "cosine":
        raise CliError("locked manifest embedding.distance must be Cosine")
    if embedding["explicit_normalization"] is not False:
        raise CliError("locked manifest embedding.explicit_normalization must be false")
    for key in ("artifact_file_count", "artifact_bytes"):
        value = embedding[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise CliError(f"locked manifest embedding.{key} must be a positive integer")
    for key in (
        "local_path",
        "device",
        "batch_size",
        "revision",
        "artifact_file_count",
        "artifact_bytes",
        "artifact_manifest_sha256",
    ):
        _required(reranker, key, "reranker")
    _required_sha256(reranker, "artifact_manifest_sha256", "reranker")
    for key in ("batch_size", "artifact_file_count", "artifact_bytes"):
        value = reranker[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise CliError(f"locked manifest reranker.{key} must be a positive integer")
    if reranker["device"] not in {"cuda", "cpu"}:
        raise CliError("locked manifest reranker.device must be cuda or cpu")
    for key in (
        "manifest_path",
        "manifest_sha256",
        "payload_manifest_sha256",
        "bm25_vocab_output",
        "bm25_vocab_sha256",
        "bm25_enabled",
    ):
        _required(index, key, "index")
    _required_sha256(index, "manifest_sha256", "index")
    _required_sha256(index, "payload_manifest_sha256", "index")
    _required_sha256(index, "bm25_vocab_sha256", "index")
    if index["bm25_enabled"] is not True:
        raise CliError("locked manifest index.bm25_enabled must be true")
    for key in (
        "selected_dir",
        "index_json_sha256",
        "canonical_file_count",
        "canonical_manifest_sha256",
    ):
        _required(schema, key, "schema")
    _required_sha256(schema, "index_json_sha256", "schema")
    _required_sha256(schema, "canonical_manifest_sha256", "schema")
    if (
        isinstance(schema["canonical_file_count"], bool)
        or not isinstance(schema["canonical_file_count"], int)
        or schema["canonical_file_count"] < 1
    ):
        raise CliError("locked manifest schema.canonical_file_count must be positive")
    if not (
        product_boundary.get("default_lite_mode") is True
        and product_boundary.get("direct_lookup_remains_default") is True
        and product_boundary.get("full_semantic_is_explicit_opt_in") is True
    ):
        raise CliError("locked manifest must preserve the LITE/Direct Lookup product boundary")

    dev_locked = _required(comparison, "dev_parameters_locked", "comparison")
    gate_status = str(_required(heldout_gate, "status", "heldout_gate")).casefold()
    if status == LOCKED_BEFORE_DEV:
        if dev_locked is not False or gate_status != "closed":
            raise CliError(
                "locked_before_dev requires dev_parameters_locked=false and heldout_gate.status=closed"
            )
        heldout_authorized = False
        heldout_evidence: dict[str, Any] | None = None
    else:
        if dev_locked is not True or gate_status not in {"open", "opened"}:
            raise CliError(
                "dev_parameters_locked_heldout_open requires "
                "dev_parameters_locked=true and an open heldout gate"
            )
        heldout_evidence = _validate_heldout_evidence(manifest, comparison)
        heldout_authorized = True
    if split in {"heldout", "all"} and not heldout_authorized:
        raise CliError(
            "heldout is closed until the dev decision and heldout gate are both frozen open"
        )
    return {
        "status": status,
        "semantic_gold_sha256": frozen_hash,
        "limited_collections": limited,
        "fanout_collections": fanout,
        "base_protocol_locked": True,
        "heldout_authorized": heldout_authorized,
        "heldout_evidence": heldout_evidence,
    }


def _resolved_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_frozen_index_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate the immutable per-point index artifact before touching Qdrant."""

    index = _section(manifest, "index")
    embedding = _section(manifest, "embedding")
    path = _resolved_path(_required(index, "manifest_path", "index"))
    expected_file_sha = _required_sha256(index, "manifest_sha256", "index")
    expected_payload_sha = _required_sha256(
        index, "payload_manifest_sha256", "index"
    )
    if not path.is_file():
        raise CliError(f"frozen index manifest does not exist: {path}")
    actual_file_sha = _sha256(path)
    if actual_file_sha != expected_file_sha:
        raise CliError(
            "frozen index manifest file SHA-256 does not match index.manifest_sha256"
        )
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"cannot read frozen index manifest {path}: {exc}") from exc
    if not isinstance(artifact, dict):
        raise CliError("frozen index manifest root must be an object")
    if artifact.get("payload_manifest_sha256") != expected_payload_sha:
        raise CliError(
            "frozen index manifest payload SHA-256 does not match "
            "index.payload_manifest_sha256"
        )

    expected_names = artifact.get("expected_collections")
    actual_names = artifact.get("actual_collections")
    if (
        artifact.get("collection_set_matches") is not True
        or not isinstance(expected_names, list)
        or not isinstance(actual_names, list)
        or set(expected_names) != _EXPECTED_COLLECTION_NAMES
        or set(actual_names) != _EXPECTED_COLLECTION_NAMES
        or len(expected_names) != len(_EXPECTED_COLLECTION_NAMES)
        or len(actual_names) != len(_EXPECTED_COLLECTION_NAMES)
    ):
        raise CliError(
            "frozen index manifest must contain exactly the eleven canonical collections"
        )
    collections = artifact.get("collections")
    if not isinstance(collections, dict) or set(collections) != _EXPECTED_COLLECTION_NAMES:
        raise CliError("frozen index manifest collection rows are incomplete")

    expected_dimension = _required(embedding, "dimension", "embedding")
    expected_distance = str(_required(embedding, "distance", "embedding")).casefold()
    if isinstance(expected_dimension, bool) or not isinstance(expected_dimension, int):
        raise CliError("locked manifest embedding.dimension must be an integer")

    summaries: dict[str, Any] = {}
    total = 0
    for name in sorted(_EXPECTED_COLLECTION_NAMES):
        row = collections[name]
        if not isinstance(row, dict):
            raise CliError(f"frozen index manifest row {name} must be an object")
        scrolled = row.get("points_scrolled")
        reported = row.get("points_count_reported")
        if (
            isinstance(scrolled, bool)
            or not isinstance(scrolled, int)
            or scrolled < 1
            or reported != scrolled
        ):
            raise CliError(f"frozen index manifest {name} has inconsistent point counts")
        collection_payload_sha = str(row.get("payload_manifest_sha256", "")).casefold()
        if not _SHA256_RE.fullmatch(collection_payload_sha):
            raise CliError(f"frozen index manifest {name} has no payload SHA-256")
        if "green" not in str(row.get("status", "")).casefold():
            raise CliError(f"frozen index manifest {name} was not green")
        config = row.get("config")
        params = config.get("params") if isinstance(config, dict) else None
        vectors = params.get("vectors") if isinstance(params, dict) else None
        dense = vectors.get("dense") if isinstance(vectors, dict) else None
        sparse = params.get("sparse_vectors") if isinstance(params, dict) else None
        if not isinstance(dense, dict) or dense.get("size") != expected_dimension:
            raise CliError(
                f"frozen index manifest {name} dense vector does not match embedding.dimension"
            )
        if str(dense.get("distance", "")).casefold() != expected_distance:
            raise CliError(
                f"frozen index manifest {name} distance does not match embedding.distance"
            )
        if not isinstance(sparse, dict) or "sparse" not in sparse:
            raise CliError(f"frozen index manifest {name} has no named sparse vector")
        total += scrolled
        summaries[name] = {
            "points_count": scrolled,
            "dense_size": dense["size"],
            "distance": dense["distance"],
            "sparse_vector_names": sorted(sparse),
            "payload_manifest_sha256": collection_payload_sha,
        }
    if artifact.get("total_points_scrolled") != total:
        raise CliError("frozen index manifest total_points_scrolled is inconsistent")
    return {
        "path": str(path.resolve()),
        "sha256": actual_file_sha,
        "payload_manifest_sha256": expected_payload_sha,
        "qdrant_url": artifact.get("qdrant_url"),
        "server": artifact.get("server"),
        "collection_names": sorted(_EXPECTED_COLLECTION_NAMES),
        "total_points": total,
        "collections": summaries,
    }


def _validate_local_artifacts(
    manifest: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Re-hash model files and cheap schema/BM25 artifacts before model load."""

    embedding = _section(manifest, "embedding")
    reranker = _section(manifest, "reranker")
    index = _section(manifest, "index")
    schema = _section(manifest, "schema")

    embedding_identity = _artifact_directory_identity(
        Path(runtime["embedding_model"])
    )
    if embedding_identity["manifest_sha256"] != embedding["model_manifest_sha256"]:
        raise CliError("embedding directory manifest SHA-256 does not match the lock")
    if embedding_identity["file_count"] != embedding["artifact_file_count"]:
        raise CliError("embedding artifact file count does not match the lock")
    if embedding_identity["bytes"] != embedding["artifact_bytes"]:
        raise CliError("embedding artifact byte count does not match the lock")
    if (
        embedding_identity["file_sha256"].get("model.safetensors")
        != embedding["model_safetensors_sha256"]
    ):
        raise CliError("embedding model.safetensors SHA-256 does not match the lock")

    reranker_identity = _artifact_directory_identity(Path(runtime["reranker_model"]))
    if reranker_identity["manifest_sha256"] != reranker["artifact_manifest_sha256"]:
        raise CliError("reranker directory manifest SHA-256 does not match the lock")
    if reranker_identity["file_count"] != reranker["artifact_file_count"]:
        raise CliError("reranker artifact file count does not match the lock")
    if reranker_identity["bytes"] != reranker["artifact_bytes"]:
        raise CliError("reranker artifact byte count does not match the lock")

    bm25_path = Path(runtime["bm25_vocab"])
    if not bm25_path.is_file() or _sha256(bm25_path) != index["bm25_vocab_sha256"]:
        raise CliError("BM25 vocabulary file SHA-256 does not match the lock")
    schema_index = Path(runtime["schema_dir"]) / "_index.json"
    if not schema_index.is_file() or _sha256(schema_index) != schema["index_json_sha256"]:
        raise CliError("schema _index.json SHA-256 does not match the lock")
    schema_identity = _schema_directory_identity(Path(runtime["schema_dir"]))
    if schema_identity["manifest_sha256"] != schema["canonical_manifest_sha256"]:
        raise CliError("schema canonical directory SHA-256 does not match the lock")
    if schema_identity["file_count"] != schema["canonical_file_count"]:
        raise CliError("schema canonical file count does not match the lock")

    # File-level hashes are intentionally omitted from the report except for
    # model.safetensors; the aggregate digest already binds every local file.
    embedding_identity["file_sha256"] = {
        "model.safetensors": embedding_identity["file_sha256"]["model.safetensors"]
    }
    reranker_identity.pop("file_sha256", None)
    return {
        "embedding": embedding_identity,
        "reranker": reranker_identity,
        "bm25_vocab": {
            "path": str(bm25_path.resolve()),
            "sha256": index["bm25_vocab_sha256"],
        },
        "schema_index": {
            "path": str(schema_index.resolve()),
            "sha256": schema["index_json_sha256"],
        },
        "schema_canonical_tree": schema_identity,
    }


def _configuration(
    args: argparse.Namespace, manifest: dict[str, Any]
) -> tuple[EvaluationConfig, dict[str, Any]]:
    comparison = _section(manifest, "comparison")
    qdrant = _section(manifest, "qdrant")
    embedding = _section(manifest, "embedding")
    index = _section(manifest, "index")
    reranker_manifest = _section(manifest, "reranker")
    schema = _section(manifest, "schema")

    limited_cli = list(_csv(args.limited_collections) or ()) if args.limited_collections else None
    fanout_cli = list(_csv(args.fanout_collections) or ()) if args.fanout_collections else None
    limited = _choose(
        "limited_collections",
        limited_cli,
        _required_collection_list(comparison, "limited_collections"),
        None,
    )
    fanout = _choose(
        "fanout_collections",
        fanout_cli,
        _required_collection_list(comparison, "fanout_collections"),
        None,
    )
    candidate_budget = int(
        _choose(
            "candidate_budget_per_collection",
            args.candidate_budget,
            _required(comparison, "candidate_budget_per_collection", "comparison"),
            None,
        )
    )
    final_top_k = int(
        _choose(
            "final_top_k",
            args.final_top_k,
            _required(comparison, "final_top_k", "comparison"),
            None,
        )
    )
    reranker_top_k = int(
        _choose(
            "reranker_top_k",
            args.reranker_top_k,
            _required(comparison, "reranker_top_k", "comparison"),
            None,
        )
    )
    weights = dict(_required(comparison, "cross_collection_rrf_weights", "comparison"))
    if comparison.get("adaptive_threshold") is not False:
        raise CliError("locked manifest must disable adaptive_threshold")
    if comparison.get("diversity_injection") is not False:
        raise CliError("locked manifest must disable diversity_injection")

    strategies = STRATEGIES if args.strategy == "all" else (args.strategy,)
    config = EvaluationConfig(
        strategies=tuple(strategies),
        candidate_budget_per_collection=candidate_budget,
        final_top_k=final_top_k,
        reranker_top_k=reranker_top_k,
        limited_collections=tuple(limited),
        fanout_collections=tuple(fanout),
        weights=weights,
        rrf_base_k=int(_required(comparison, "rrf_base_k", "comparison")),
        adaptive_threshold=False,
        diversity_injection=False,
        bm25_enabled=True,
    )
    embedding_device = str(_required(embedding, "device", "embedding"))
    reranker_device = str(_required(reranker_manifest, "device", "reranker"))
    if embedding_device != reranker_device:
        raise CliError("locked embedding.device and reranker.device must match")
    runtime = {
        "qdrant_host": str(
            _choose("qdrant_host", args.qdrant_host, _required(qdrant, "host", "qdrant"), None)
        ),
        "qdrant_port": int(
            _choose("qdrant_port", args.qdrant_port, _required(qdrant, "port", "qdrant"), None)
        ),
        "embedding_model": str(
            _choose(
                "embedding_model",
                args.embedding_model,
                _required(embedding, "model", "embedding"),
                None,
            )
        ),
        "reranker_model": str(
            _choose(
                "reranker_model",
                args.reranker_model,
                _required(reranker_manifest, "local_path", "reranker"),
                None,
            )
        ),
        "bm25_vocab": _resolved_path(
            _choose(
                "bm25_vocab",
                args.bm25_vocab,
                _required(index, "bm25_vocab_output", "index"),
                None,
            )
        ),
        "schema_dir": _resolved_path(
            _choose(
                "schema_dir",
                args.schema_dir,
                _required(schema, "selected_dir", "schema"),
                None,
            )
        ),
        "timeout_seconds": float(
            _choose(
                "timeout_seconds",
                args.timeout_seconds,
                _required(qdrant, "timeout_seconds", "qdrant"),
                None,
            )
        ),
        "device": _choose("device", args.device, embedding_device, None),
        "reranker_batch_size": int(
            _choose(
                "reranker_batch_size",
                args.reranker_batch_size,
                _required(reranker_manifest, "batch_size", "reranker"),
                None,
            )
        ),
    }
    embedding_path = _resolved_path(runtime["embedding_model"])
    if not embedding_path.is_dir():
        raise CliError(
            "stage-two embedding_model must be a pre-existing local directory; "
            "the runner never downloads models implicitly"
        )
    runtime["embedding_model"] = str(embedding_path.resolve())
    reranker_path = _resolved_path(runtime["reranker_model"])
    if not reranker_path.is_dir():
        raise CliError(
            "the locked reranker must be a pre-downloaded local model directory"
        )
    runtime["reranker_model"] = str(reranker_path.resolve())
    return config, runtime


def _needed_collections(cases: Sequence[GoldCase], config: EvaluationConfig) -> set[str]:
    needed = set(config.limited_collections) | set(config.fanout_collections)
    for case in cases:
        if case.api_filters.plugin:
            needed.add("plugins")
        needed.update(case.api_filters.collections)
    return needed


def _validate_index(
    qdrant_identity: dict[str, Any],
    dense_dimension: int | None,
    needed: set[str],
    frozen_index: dict[str, Any],
    manifest: dict[str, Any],
    bm25_identity: dict[str, Any],
) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    fatal: list[str] = []
    qdrant = _section(manifest, "qdrant")
    embedding = _section(manifest, "embedding")
    index = _section(manifest, "index")
    collections = qdrant_identity.get("collections", {})
    actual_names = qdrant_identity.get("actual_collection_names")
    frozen_names = frozen_index["collection_names"]
    if actual_names != frozen_names:
        fatal.append(
            f"live collection set {actual_names!r} != frozen collection set {frozen_names!r}"
        )
    if qdrant_identity.get("collection_set_matches") is not True:
        fatal.append("live Qdrant collection registry is incomplete or has extra collections")
    expected_url = f"http://{qdrant['host']}:{qdrant['port']}"
    if frozen_index.get("qdrant_url") != expected_url:
        fatal.append("frozen index qdrant_url does not match locked qdrant host/port")
    server = qdrant_identity.get("server", {})
    if not isinstance(server, dict):
        fatal.append("live Qdrant server identity is unavailable")
    else:
        if str(server.get("version")) != str(qdrant["server_version"]):
            fatal.append("live Qdrant version does not match locked server_version")
        if str(server.get("commit")) != str(qdrant["server_commit"]):
            fatal.append("live Qdrant commit does not match locked server_commit")
    if dense_dimension != embedding["dimension"]:
        fatal.append(
            f"loaded embedding dimension {dense_dimension!r} != locked dimension "
            f"{embedding['dimension']!r}"
        )
    if bm25_identity.get("vocab_sha256") != index["bm25_vocab_sha256"]:
        fatal.append("loaded BM25 vocabulary SHA-256 does not match the locked index")

    live_by_name = {
        identity.get("name"): (key, identity)
        for key, identity in collections.items()
        if isinstance(identity, dict) and identity.get("name")
    }
    for name in frozen_names:
        key, identity = live_by_name.get(name, (name.removeprefix("c3_"), {}))
        frozen = frozen_index["collections"][name]
        identity = collections.get(key, {})
        failures: list[str] = []
        if not identity.get("present"):
            failures.append("collection missing")
        if identity.get("inspection_error"):
            failures.append(str(identity["inspection_error"]))
        if str(identity.get("status", "")).casefold() != "green":
            failures.append(f"collection status is {identity.get('status')!r}, not green")
        size = identity.get("dense", {}).get("size")
        if dense_dimension is not None and size != dense_dimension:
            failures.append(f"dense dimension {size!r} != model dimension {dense_dimension}")
        sparse_names = identity.get("sparse_vector_names", [])
        if "sparse" not in sparse_names:
            failures.append("named sparse vector is missing")
        if identity.get("points_count") != frozen["points_count"]:
            failures.append(
                f"live points_count {identity.get('points_count')!r} != frozen "
                f"{frozen['points_count']!r}"
            )
        if str(identity.get("dense", {}).get("distance", "")).casefold() != str(
            frozen["distance"]
        ).casefold():
            failures.append("live distance does not match frozen index")
        rows[key] = {"passes": not failures, "failures": failures}
        fatal.extend(f"{key}: {failure}" for failure in failures)
    missing_needed = needed - set(rows)
    fatal.extend(f"{key}: required collection is absent from frozen index" for key in missing_needed)
    return {
        "passes": not fatal,
        "frozen_payload_identity": {
            "manifest_path": frozen_index["path"],
            "manifest_sha256": frozen_index["sha256"],
            "payload_manifest_sha256": frozen_index["payload_manifest_sha256"],
            "total_points": frozen_index["total_points"],
        },
        "live_parity_scope": [
            "server version and commit",
            "exact collection set",
            "per-collection point count",
            "named dense dimension and distance",
            "named sparse vector presence",
            "BM25 vocabulary SHA-256",
        ],
        "collections": rows,
        "fatal_failures": fatal,
    }


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _print_human(report: dict[str, Any]) -> None:
    print(
        f"semantic eval: split={report['run']['split']} "
        f"cases={report['run']['case_count']} strategies={','.join(report['run']['strategies'])}"
    )
    for strategy, summary in report.get("summaries", {}).items():
        overall = summary["overall"]
        quality = overall["quality"]["semantic_pre_lookup"]
        latency = overall["latency"]["warm"]
        print(
            f"  {strategy:8s} Hit@5={quality['hit_at_5']} "
            f"Recall@10={quality['recall_at_10']} MRR={quality['mrr']} "
            f"nDCG@10={quality['ndcg_at_10']} warm-p95={latency['p95_ms']}ms "
            f"errors={overall['query_error_rate']}"
        )
    print(f"report: {report['output_path']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen full-semantic comparison against real Qdrant. "
            "Mock adapters are reserved for pytest contract tests."
        )
    )
    parser.add_argument("--strategy", choices=(*STRATEGIES, "all"), default="all")
    parser.add_argument("--split", choices=("dev", "heldout", "all"), default="dev")
    parser.add_argument(
        "--fixture", type=Path, default=ROOT / "tests" / "fixtures" / "semantic_gold.jsonl"
    )
    parser.add_argument("--manifest", type=Path, required=True, help="locked experiment manifest")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--qdrant-host")
    parser.add_argument("--qdrant-port", type=int)
    parser.add_argument("--embedding-model")
    parser.add_argument("--reranker-model")
    parser.add_argument("--bm25-vocab")
    parser.add_argument("--schema-dir")
    parser.add_argument("--limited-collections", help="comma-separated; must match manifest")
    parser.add_argument("--fanout-collections", help="comma-separated; must match manifest")
    parser.add_argument("--candidate-budget", type=int)
    parser.add_argument("--final-top-k", type=int)
    parser.add_argument("--reranker-top-k", type=int)
    parser.add_argument("--reranker-batch-size", type=int)
    parser.add_argument("--device", choices=("cuda", "cpu"))
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--verbose", action="store_true")
    return parser


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    started_wall = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    fixture_path = args.fixture if args.fixture.is_absolute() else ROOT / args.fixture
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    fixture_sha = _sha256(fixture_path)
    manifest, manifest_sha = _read_json(manifest_path)
    lock = _lock_validation(manifest, fixture_sha, args.split)
    frozen_index = _load_frozen_index_manifest(manifest)
    cases = load_fixture(fixture_path, args.split)
    config, runtime = _configuration(args, manifest)
    local_artifacts = _validate_local_artifacts(manifest, runtime)
    output = args.output or (
        DEFAULT_STAGE_DIR / f"semantic-{args.split}-{args.strategy}.json"
    )
    if not output.is_absolute():
        output = ROOT / output

    resources_before_load = resource_snapshot()
    dense = LiveDenseEncoder(runtime["embedding_model"], device=runtime["device"])
    sparse = LiveSparseEncoder(runtime["bm25_vocab"])
    lookup = LiveLookupProbe(runtime["schema_dir"])
    reranker = (
        LiveCrossEncoder(
            runtime["reranker_model"],
            device=runtime["device"],
            batch_size=runtime["reranker_batch_size"],
        )
        if "rerank" in config.strategies
        else None
    )
    dense.prepare()
    resources_after_embedding_load = resource_snapshot()
    sparse.prepare()
    lookup.prepare()
    if reranker is not None:
        reranker.prepare()
    resources_after_all_loads = resource_snapshot()
    bm25_identity = sparse.identity()

    backend = LiveQdrantBackend(
        runtime["qdrant_host"],
        runtime["qdrant_port"],
        timeout_seconds=runtime["timeout_seconds"],
    )
    try:
        qdrant_identity = backend.identity()
    except Exception as exc:
        qdrant_identity = {
            "host": runtime["qdrant_host"],
            "port": runtime["qdrant_port"],
            "connection_error": f"{type(exc).__name__}: {exc}",
            "collections": {},
        }
    index_validation = _validate_index(
        qdrant_identity,
        dense.dimension,
        _needed_collections(cases, config),
        frozen_index,
        manifest,
        bm25_identity,
    )
    base_report: dict[str, Any] = {
        "schema_version": "construct3-semantic-eval-report-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_path": str(output.resolve()),
        "protocol": {
            "path": str(manifest_path.resolve()),
            "sha256": manifest_sha,
            "lock_validation": lock,
            "manifest": manifest,
        },
        "fixture": {
            "path": str(fixture_path.resolve()),
            "sha256": fixture_sha,
            "line_count": len(load_fixture(fixture_path, "all")),
            "selected_count": len(cases),
            "split": args.split,
        },
        "configuration": config.to_dict(),
        "runtime": runtime_identity(),
        "models": {
            "embedding": dense.identity(),
            "bm25": bm25_identity,
            "reranker": reranker.identity() if reranker is not None else {"enabled": False},
            "lookup": lookup.identity(),
        },
        "local_artifact_validation": local_artifacts,
        "qdrant": qdrant_identity,
        "frozen_index_manifest": frozen_index,
        "index_validation": index_validation,
        "model_load_resources": {
            "before": resources_before_load,
            "after_embedding": resources_after_embedding_load,
            "after_all_models": resources_after_all_loads,
        },
    }
    if not index_validation["passes"]:
        base_report.update(
            {
                "status": "preflight_failed_no_retrieval_run",
                "run": {
                    "split": args.split,
                    "strategies": list(config.strategies),
                    "case_count": len(cases),
                    "elapsed_seconds": time.perf_counter() - started_perf,
                },
                "queries": [],
                "summaries": {},
                "paired": {},
            }
        )
        _atomic_json(output, base_report)
        return 2, base_report

    runner = EvaluationRunner(
        config=config,
        encoder=dense,
        sparse_encoder=sparse,
        backend=backend,
        reranker=reranker,
        lookup_probe=lookup,
        resource_probe=resource_snapshot,
    )
    query_rows = runner.run(cases)
    summaries = stratified_summaries(query_rows, config.strategies)
    paired = paired_comparisons(query_rows, config.strategies)
    shared_candidate_pairs = {
        key: value["candidate_batch_digest_all_equal"]
        for key, value in paired.items()
        if key in {"rrf_vs_fanout", "rerank_vs_rrf"}
    }
    operational_errors = any(
        row["strategies"][strategy]["errors"]
        for row in query_rows
        for strategy in config.strategies
    )
    contract_failures = any(
        row["routes"]["contract_failures"]
        or row["strategies"][strategy]["contract_failures"]
        for row in query_rows
        for strategy in config.strategies
    ) or not all(shared_candidate_pairs.values())
    elapsed = time.perf_counter() - started_perf
    report = {
        **base_report,
        "status": (
            "complete_with_errors"
            if operational_errors
            else "complete_with_contract_failures"
            if contract_failures
            else "complete"
        ),
        "run": {
            "split": args.split,
            "strategies": list(config.strategies),
            "case_count": len(cases),
            "started_at": started_wall.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": elapsed,
            "heldout_was_authorized": lock["heldout_authorized"],
            "mock_quality_claim": False,
        },
        "queries": query_rows,
        "summaries": summaries,
        "paired": paired,
        "comparison_contract": {
            "fanout_rrf_rerank_candidate_batches_shared": all(
                shared_candidate_pairs.values()
            ),
            "paired_digest_checks": shared_candidate_pairs,
            "query_route_contract_failure_ids": [
                row["case"]["id"]
                for row in query_rows
                if row["routes"]["contract_failures"]
            ],
        },
        "resources_after_run": resource_snapshot(),
    }
    _atomic_json(output, report)
    return (0 if report["status"] == "complete" else 1), report


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code, report = run(args)
    except (CliError, FixtureError, FileNotFoundError, ValueError) as exc:
        print(f"semantic evaluation configuration error: {exc}", file=sys.stderr)
        return 2
    _print_human(report)
    if args.verbose:
        for row in report.get("queries", []):
            print(f"\n{row['case']['id']}: {row['case']['query']}")
            for strategy, result in row["strategies"].items():
                print(
                    f"  {strategy}: {result['ordered_stable_ids']} "
                    f"errors={result['errors']}"
                )
    return code
