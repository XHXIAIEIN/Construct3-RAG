"""Offline contract tests for the independent stage-two evaluator.

These fakes verify comparison mechanics only.  They are intentionally not
reported as retrieval-quality evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.semantic_eval.core import (
    BackendPoint,
    BackendSearchResult,
    EvaluationConfig,
    EvaluationRunner,
)
from tests.semantic_eval.cli import (
    CliError,
    _artifact_directory_identity,
    _load_frozen_index_manifest,
    _lock_validation,
    _schema_directory_identity,
    _validate_local_artifacts,
)
from tests.semantic_eval.live import LiveQdrantBackend
from tests.semantic_eval.metrics import (
    evaluate_ranking,
    paired_comparisons,
    stratified_summaries,
)
from tests.semantic_eval.models import (
    ApiFilters,
    FixtureError,
    GoldCase,
    KNOWN_COLLECTION_KEYS,
    ResultJudgment,
    load_fixture,
)
from tests.semantic_eval.stable_ids import stable_result_id


def _case(
    *,
    relevant: tuple[str, ...] = ("plugins|plugin-reference/sprite|sprite-actions",),
    filters: ApiFilters = ApiFilters(),
    lookup_route: str = "miss",
    api_route: str = "auto",
    dedup: tuple[dict, ...] = (),
) -> GoldCase:
    return GoldCase(
        id="semantic-test-01",
        query="Sprite animation",
        locale="en-US",
        task_family="test",
        style_tags=("language-en",),
        parent_query_id=None,
        expected_api_route=api_route,
        expected_lookup_route=lookup_route,
        expected_semantic_route="required",
        relevant_results=tuple(ResultJudgment(item) for item in relevant),
        forbidden_results=(),
        allowed_alternatives=(),
        graded_relevance={item: 3.0 for item in relevant},
        max_rank=10 if relevant else None,
        critical=False,
        schema_version="r495",
        source_path="evidence.md" if relevant else None,
        rationale="offline evaluator contract",
        split="dev",
        api_filters=filters,
        limited_collections=(),
        dedup_expectations=dedup,
        fixture_line=1,
    )


class _Encoder:
    def __init__(self):
        self.calls: list[str] = []

    def encode_query(self, query: str):
        self.calls.append(query)
        return [1.0, 2.0, 3.0]


class _Sparse:
    def __init__(self):
        self.calls: list[str] = []

    def encode_query(self, query: str):
        self.calls.append(query)
        return {3: 0.5}


class _Backend:
    def __init__(self, points: dict[str, list[BackendPoint]]):
        self.points = points
        self.calls: list[tuple] = []

    def search(self, collection_key, dense_vector, sparse_vector, limit, filters):
        self.calls.append((collection_key, tuple(dense_vector), dict(sparse_vector), limit, filters))
        return BackendSearchResult(
            collection_name=f"c3_{collection_key}",
            points=tuple(self.points.get(collection_key, ()))[:limit],
            elapsed_ms=1.0,
        )


class _FilteringBackend(_Backend):
    def search(self, collection_key, dense_vector, sparse_vector, limit, filters):
        raw = super().search(
            collection_key, dense_vector, sparse_vector, limit, filters
        )
        points = raw.points
        if filters.section_types:
            allowed = set(filters.section_types)
            points = tuple(
                point for point in points if point.payload.get("section_type") in allowed
            )
        return BackendSearchResult(
            collection_name=raw.collection_name,
            points=points,
            elapsed_ms=raw.elapsed_ms,
        )


class _Reranker:
    def __init__(self):
        self.calls: list[list[str]] = []

    def predict(self, query, texts):
        self.calls.append(list(texts))
        return list(range(len(texts)))


class _Lookup:
    def __init__(self, stable_ids=(), route="miss"):
        self.stable_ids = list(stable_ids)
        self.route = route

    def observe(self, case):
        return {
            "route": self.route,
            "stable_ids": self.stable_ids,
            "matches": [],
            "elapsed_ms": 0.2,
            "error": None,
        }


def _point(point_id: str, score: float, **payload) -> BackendPoint:
    return BackendPoint(point_id, payload.pop("text", point_id), score, payload)


def _locked_manifest(*, fixture_sha: str = "a" * 64) -> dict:
    return {
        "status": "locked_before_dev",
        "product_boundary": {
            "default_lite_mode": True,
            "direct_lookup_remains_default": True,
            "full_semantic_is_explicit_opt_in": True,
        },
        "comparison": {
            "strategies": ["limited", "fanout", "rrf", "rerank"],
            "semantic_gold_sha256": fixture_sha,
            "limited_collections": ["plugins"],
            "fanout_collections": ["plugins"],
            "candidate_budget_per_collection": 10,
            "final_top_k": 10,
            "reranker_top_k": 20,
            "rrf_base_k": 60,
            "adaptive_threshold": False,
            "diversity_injection": False,
            "cross_collection_rrf_weights": {"plugins": 1.0},
            "dev_parameters_locked": False,
        },
        "heldout_gate": {"status": "closed"},
        "qdrant": {
            "host": "127.0.0.1",
            "port": 6334,
            "timeout_seconds": 60.0,
            "server_version": "1.17.0",
            "server_commit": "c" * 40,
            "image_digest": "sha256:" + "d" * 64,
        },
        "embedding": {
            "model": "embedding",
            "device": "cuda",
            "dimension": 3,
            "distance": "Cosine",
            "explicit_normalization": False,
            "artifact_file_count": 2,
            "artifact_bytes": 2,
            "model_safetensors_sha256": "e" * 64,
            "model_manifest_sha256": "f" * 64,
        },
        "reranker": {
            "local_path": "reranker",
            "device": "cuda",
            "batch_size": 8,
            "revision": "1" * 40,
            "artifact_file_count": 2,
            "artifact_bytes": 2,
            "artifact_manifest_sha256": "2" * 64,
        },
        "index": {
            "manifest_path": "index-manifest.json",
            "manifest_sha256": "3" * 64,
            "payload_manifest_sha256": "4" * 64,
            "bm25_vocab_output": "bm25.msgpack",
            "bm25_vocab_sha256": "5" * 64,
            "bm25_enabled": True,
        },
        "schema": {
            "selected_dir": "schemas",
            "index_json_sha256": "6" * 64,
            "canonical_file_count": 1,
            "canonical_manifest_sha256": "7" * 64,
        },
    }


def _open_manifest_with_evidence(tmp_path: Path) -> dict:
    manifest = _locked_manifest()
    dev_protocol_path = tmp_path / "protocol-before-dev.json"
    dev_protocol_path.write_text('{"status":"locked_before_dev"}', encoding="utf-8")
    protocol_sha = hashlib.sha256(dev_protocol_path.read_bytes()).hexdigest()
    comparison = manifest["comparison"]
    configuration = {
        "strategies": ["limited", "fanout", "rrf", "rerank"],
        "candidate_budget_per_collection": 10,
        "final_top_k": 10,
        "reranker_top_k": 20,
        "limited_collections": ["plugins"],
        "fanout_collections": ["plugins"],
        "weights": {"plugins": 1.0},
        "rrf_base_k": 60,
        "adaptive_threshold": False,
        "diversity_injection": False,
        "bm25_enabled": True,
    }
    report = {
        "status": "complete",
        "run": {
            "split": "dev",
            "strategies": ["limited", "fanout", "rrf", "rerank"],
        },
        "fixture": {"sha256": "a" * 64},
        "protocol": {"sha256": protocol_sha, "path": str(dev_protocol_path)},
        "configuration": configuration,
        "index_validation": {"passes": True},
        "queries": [{"case": {"split": "dev"}}],
        "paired": {
            "fanout_vs_limited": {"candidate_batch_digest_all_equal": False},
            "rrf_vs_fanout": {"candidate_batch_digest_all_equal": True},
            "rerank_vs_rrf": {"candidate_batch_digest_all_equal": True},
        },
    }
    report_path = tmp_path / "dev-report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    report_sha = hashlib.sha256(report_path.read_bytes()).hexdigest()
    product_decision = "retain LITE and Direct Lookup defaults"
    decision = {
        "status": "locked_before_heldout",
        "dev_report_sha256": report_sha,
        "dev_protocol_sha256": protocol_sha,
        "parameters_changed_after_dev": False,
        "dev_product_decision": product_decision,
        "product_boundary": manifest["product_boundary"],
    }
    decision_path = tmp_path / "dev-decision.json"
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    decision_sha = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    manifest["status"] = "dev_parameters_locked_heldout_open"
    comparison.update(
        {
            "dev_parameters_locked": True,
            "dev_report_path": str(report_path),
            "dev_report_sha256": report_sha,
            "dev_protocol_sha256": protocol_sha,
            "dev_decision_path": str(decision_path),
            "dev_decision_sha256": decision_sha,
            "dev_product_decision": product_decision,
        }
    )
    manifest["heldout_gate"]["status"] = "open"
    return manifest


def test_stable_ids_cover_all_frozen_source_types():
    assert stable_result_id(
        "c3_ace",
        {"plugin_type": "behavior", "plugin_name": "Tween", "ace_type": "actions", "ace_id": "start"},
    ) == "ace|behavior|tween|action|start"
    assert stable_result_id(
        "plugins", {"source": "plugin-reference/Array.md", "h2_heading": "Array expressions"}
    ) == "plugins|plugin-reference/array|array-expressions"
    assert stable_result_id(
        "addon_sdk", {"source": "addon-sdk/plugin/example"}
    ) == "addon_sdk|addon-sdk/plugin/example|root"
    assert stable_result_id("examples", {"slug": "Platformer-Basics"}) == "examples|platformer-basics"
    assert stable_result_id("effects", {"effect_id": "Pixelate"}) == "effects|pixelate"
    assert stable_result_id(
        "terms", {"path": ["text", "plugins", "_common", "actions", "destroy", "list-name"]}
    ) == "terms|_common|action|destroy"


def test_fixture_loader_accepts_negative_null_routes_filters_and_dedup(tmp_path: Path):
    row = {
        "id": "negative-01",
        "query": "QuantumSprite 有哪些 actions",
        "locale": "zh-CN",
        "task_family": "unknown",
        "style_tags": ["mixed"],
        "parent_query_id": "direct-parent",
        "expected_api_route": "semantic",
        "expected_lookup_route": "bypass",
        "expected_semantic_route": "required",
        "api_filters": {"collections": ["effects"]},
        "relevant_results": [],
        "forbidden_results": [{"id": "ace|plugin|sprite|action|set-animation", "within_top_k": 5}],
        "allowed_alternatives": [],
        "graded_relevance": {},
        "max_rank": None,
        "critical": True,
        "schema_version": "r495",
        "source_path": None,
        "rationale": "unknown entity must not collapse to Sprite",
        "split": "heldout",
        "dedup_expectations": [
            {"id": "ACE|PLUGIN|SPRITE|ACTION|SET-ANIMATION", "max_occurrences_total": 1}
        ],
    }
    path = tmp_path / "semantic.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    case = load_fixture(path)[0]
    assert case.max_rank is None
    assert case.api_filters.collections == ("effects",)
    assert case.dedup_expectations[0]["id"] == "ace|plugin|sprite|action|set-animation"


def test_fixture_loader_rejects_positive_case_with_null_max_rank(tmp_path: Path):
    row = {
        "id": "bad-01",
        "query": "q",
        "locale": "en-US",
        "task_family": "x",
        "style_tags": [],
        "expected_api_route": "semantic",
        "relevant_results": ["effects|blur"],
        "forbidden_results": [],
        "allowed_alternatives": [],
        "graded_relevance": {"effects|blur": 3},
        "max_rank": None,
        "critical": False,
        "schema_version": "r495",
        "source_path": "effect.json",
        "rationale": "bad rank gate",
        "split": "dev",
    }
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(FixtureError, match="max_rank"):
        load_fixture(path)


def test_locked_before_dev_manifest_does_not_open_heldout(tmp_path: Path):
    manifest = _locked_manifest()
    assert _lock_validation(manifest, "a" * 64, "dev")["base_protocol_locked"]
    with pytest.raises(CliError, match="heldout is closed"):
        _lock_validation(manifest, "a" * 64, "heldout")

    manifest = _open_manifest_with_evidence(tmp_path)
    assert _lock_validation(manifest, "a" * 64, "heldout")["heldout_authorized"]

    Path(manifest["comparison"]["dev_decision_path"]).write_text(
        '{"tampered":true}', encoding="utf-8"
    )
    with pytest.raises(CliError, match="dev decision SHA-256"):
        _lock_validation(manifest, "a" * 64, "heldout")


def test_protocol_lock_rejects_fuzzy_status_and_missing_runtime_identity():
    manifest = _locked_manifest()
    manifest["status"] = "not_really_locked"
    with pytest.raises(CliError, match="status must be exactly"):
        _lock_validation(manifest, "a" * 64, "dev")

    manifest = _locked_manifest()
    del manifest["index"]["payload_manifest_sha256"]
    with pytest.raises(CliError, match="index.payload_manifest_sha256"):
        _lock_validation(manifest, "a" * 64, "dev")

    manifest = _locked_manifest()
    del manifest["reranker"]["artifact_bytes"]
    with pytest.raises(CliError, match="reranker.artifact_bytes"):
        _lock_validation(manifest, "a" * 64, "dev")


def test_local_model_artifacts_are_rehashed_and_tampering_is_rejected(tmp_path: Path):
    embedding_dir = tmp_path / "embedding"
    reranker_dir = tmp_path / "reranker"
    schema_dir = tmp_path / "schemas"
    embedding_dir.mkdir()
    reranker_dir.mkdir()
    schema_dir.mkdir()
    (embedding_dir / "model.safetensors").write_bytes(b"embedding-weights")
    (embedding_dir / "config.json").write_text("{}", encoding="utf-8")
    (embedding_dir / ".cache").mkdir()
    (embedding_dir / ".cache" / "ignored").write_bytes(b"ignored")
    (reranker_dir / "model.safetensors").write_bytes(b"reranker-weights")
    (reranker_dir / "config.json").write_text("{}", encoding="utf-8")
    (schema_dir / "_index.json").write_text("{}", encoding="utf-8")
    bm25_path = tmp_path / "bm25.msgpack"
    bm25_path.write_bytes(b"bm25")

    embedding_identity = _artifact_directory_identity(embedding_dir)
    reranker_identity = _artifact_directory_identity(reranker_dir)
    manifest = _locked_manifest()
    manifest["embedding"].update(
        {
            "model": str(embedding_dir),
            "artifact_file_count": embedding_identity["file_count"],
            "artifact_bytes": embedding_identity["bytes"],
            "model_safetensors_sha256": embedding_identity["file_sha256"][
                "model.safetensors"
            ],
            "model_manifest_sha256": embedding_identity["manifest_sha256"],
        }
    )
    manifest["reranker"].update(
        {
            "local_path": str(reranker_dir),
            "artifact_file_count": reranker_identity["file_count"],
            "artifact_bytes": reranker_identity["bytes"],
            "artifact_manifest_sha256": reranker_identity["manifest_sha256"],
        }
    )
    manifest["index"].update(
        {
            "bm25_vocab_output": str(bm25_path),
            "bm25_vocab_sha256": hashlib.sha256(b"bm25").hexdigest(),
        }
    )
    manifest["schema"].update(
        {
            "selected_dir": str(schema_dir),
            "index_json_sha256": hashlib.sha256(b"{}").hexdigest(),
            "canonical_manifest_sha256": _schema_directory_identity(schema_dir)[
                "manifest_sha256"
            ],
        }
    )
    runtime = {
        "embedding_model": str(embedding_dir),
        "reranker_model": str(reranker_dir),
        "bm25_vocab": bm25_path,
        "schema_dir": schema_dir,
    }
    result = _validate_local_artifacts(manifest, runtime)
    assert result["embedding"]["file_count"] == 2
    assert result["reranker"]["manifest_sha256"] == reranker_identity["manifest_sha256"]

    (reranker_dir / "config.json").write_text('{"tampered":true}', encoding="utf-8")
    with pytest.raises(CliError, match="reranker directory manifest"):
        _validate_local_artifacts(manifest, runtime)


def test_frozen_index_manifest_binds_payload_collection_counts_and_config(tmp_path: Path):
    names = sorted(f"c3_{key}" for key in KNOWN_COLLECTION_KEYS)
    payload_sha = "8" * 64
    artifact = {
        "qdrant_url": "http://127.0.0.1:6334",
        "server": {"version": "1.17.0", "commit": "c" * 40},
        "expected_collections": names,
        "actual_collections": names,
        "collection_set_matches": True,
        "collections": {
            name: {
                "status": "green",
                "points_count_reported": 1,
                "points_scrolled": 1,
                "payload_manifest_sha256": "9" * 64,
                "config": {
                    "params": {
                        "vectors": {"dense": {"size": 3, "distance": "Cosine"}},
                        "sparse_vectors": {"sparse": {}},
                    }
                },
            }
            for name in names
        },
        "total_points_scrolled": len(names),
        "payload_manifest_sha256": payload_sha,
    }
    path = tmp_path / "index-manifest.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    manifest = _locked_manifest()
    manifest["index"].update(
        {
            "manifest_path": str(path),
            "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "payload_manifest_sha256": payload_sha,
        }
    )
    frozen = _load_frozen_index_manifest(manifest)
    assert frozen["total_points"] == len(names)
    assert frozen["collections"]["c3_plugins"]["dense_size"] == 3

    manifest["index"]["payload_manifest_sha256"] = "0" * 64
    with pytest.raises(CliError, match="payload SHA-256"):
        _load_frozen_index_manifest(manifest)


def test_all_strategies_share_one_embedding_and_one_fanout_candidate_batch():
    points = {
        "plugins": [
            _point("p1", 0.90, source="plugin-reference/sprite.md", h2_heading="Sprite actions"),
            _point("p2", 0.80, source="plugin-reference/sprite.md", h2_heading="Sprite conditions"),
            _point("p3", 0.70, source="plugin-reference/sprite.md", h2_heading="Sprite actions"),
        ],
        "ace": [
            _point(
                "a1",
                0.75,
                plugin_type="plugin",
                plugin_name="sprite",
                ace_type="action",
                ace_id="set-animation",
            )
        ],
        "examples": [_point("e1", 0.95, slug="sprite-animations")],
    }
    encoder, sparse, backend, reranker = _Encoder(), _Sparse(), _Backend(points), _Reranker()
    runner = EvaluationRunner(
        config=EvaluationConfig(
            limited_collections=("plugins",),
            fanout_collections=("plugins", "ace", "examples"),
            final_top_k=3,
        ),
        encoder=encoder,
        sparse_encoder=sparse,
        backend=backend,
        reranker=reranker,
        lookup_probe=_Lookup(),
        resource_probe=lambda: {"process_rss_bytes": 123, "cuda_allocated_bytes": 456},
    )
    row = runner.run([_case()])[0]
    assert encoder.calls == ["Sprite animation"]
    assert sparse.calls == ["Sprite animation"]
    assert [call[0] for call in backend.calls] == ["plugins", "ace", "examples"]
    assert all(call[3] == 10 for call in backend.calls)
    strategies = row["strategies"]
    assert strategies["fanout"]["candidate_batch_digest"] == strategies["rrf"]["candidate_batch_digest"]
    assert strategies["rrf"]["candidate_batch_digest"] == strategies["rerank"]["candidate_batch_digest"]
    assert strategies["limited"]["candidate_batch_digest"] != strategies["fanout"]["candidate_batch_digest"]
    assert reranker.calls and len(reranker.calls[0]) <= 20
    assert row["candidate_batch"]["embedding_call_count"] == 1
    assert row["candidate_batch"]["sparse_encoding_call_count"] == 1
    assert row["resources"]["before"]["process_rss_bytes"] == 123
    for result in strategies.values():
        assert len(result["ordered_stable_ids"]) <= 3
        assert len(result["ordered_stable_ids"]) == len(set(result["ordered_stable_ids"]))
        assert set(("embedding", "sparse", "qdrant", "fusion", "reranker", "semantic_total")) <= set(
            result["timings_ms"]
        )
    assert strategies["fanout"]["exact_dedup"]["removed_ids"] == [
        "plugins|plugin-reference/sprite|sprite-actions"
    ]


def test_weighted_rrf_exactly_mirrors_frozen_production_formula():
    runner = EvaluationRunner(
        config=EvaluationConfig(
            strategies=("rrf",),
            limited_collections=("plugins",),
            fanout_collections=("plugins", "examples"),
            weights={"plugins": 1.0, "examples": 0.6},
            final_top_k=2,
        ),
        encoder=_Encoder(),
        sparse_encoder=_Sparse(),
        backend=_Backend(
            {
                "plugins": [
                    _point(
                        "p", 0.5, source="plugin-reference/sprite.md", h2_heading="Sprite"
                    )
                ],
                "examples": [_point("e", 0.99, slug="sprite")],
            }
        ),
        lookup_probe=_Lookup(),
    )
    result = runner.run([_case()])[0]["strategies"]["rrf"]
    scores = {
        row["stable_id"]: row["fused_score"] for row in result["ordered_results"]
    }
    assert scores["plugins|plugin-reference/sprite|sprite"] == pytest.approx(1 / 61)
    assert scores["examples|sprite"] == pytest.approx(1 / 101)
    assert "k=round" in runner.config.to_dict()["weighted_rrf_formula"]


def test_lookup_exact_dedup_backfills_and_checks_expectation():
    duplicate = "ace|plugin|sprite|action|set-animation"
    points = {
        "ace": [
            _point(
                "a1", 0.9, plugin_type="plugin", plugin_name="sprite", ace_type="action", ace_id="set-animation"
            ),
            _point(
                "a2", 0.8, plugin_type="plugin", plugin_name="sprite", ace_type="action", ace_id="stop-animation"
            ),
            _point(
                "a3", 0.7, plugin_type="plugin", plugin_name="sprite", ace_type="action", ace_id="start-animation"
            ),
        ]
    }
    runner = EvaluationRunner(
        config=EvaluationConfig(
            strategies=("limited",),
            limited_collections=("ace",),
            fanout_collections=("ace",),
            final_top_k=2,
        ),
        encoder=_Encoder(),
        sparse_encoder=_Sparse(),
        backend=_Backend(points),
        lookup_probe=_Lookup([duplicate], route="hit"),
    )
    case = _case(
        relevant=(duplicate,),
        lookup_route="hit",
        dedup=(({"id": duplicate, "max_occurrences_total": 1, "forbidden_in_route": "semantic"}),),
    )
    result = runner.run([case])[0]["strategies"]["limited"]
    assert duplicate in result["ordered_pre_lookup_stable_ids"]
    assert duplicate not in result["ordered_stable_ids"]
    assert result["ordered_stable_ids"] == [
        "ace|plugin|sprite|action|stop-animation",
        "ace|plugin|sprite|action|start-animation",
    ]
    assert result["exact_dedup"]["backfilled_ids"] == [
        "ace|plugin|sprite|action|start-animation"
    ]
    assert result["dedup_expectations"]["passes"]


def test_reranker_keeps_rrf_tail_for_exact_lookup_backfill():
    class FlatReranker:
        def predict(self, query, texts):
            return [0.0] * len(texts)

    points = {
        collection: [
            _point(
                f"{collection}-{index}",
                1.0 - index / 100,
                source=f"{collection}/doc-{index}.md",
            )
            for index in range(10)
        ]
        for collection in ("plugins", "guide", "interface")
    }
    lookup_ids = [
        f"{collection}|{collection}/doc-{index}|root"
        for index in range(5)
        for collection in ("plugins", "guide", "interface")
    ]
    runner = EvaluationRunner(
        config=EvaluationConfig(
            strategies=("rerank",),
            limited_collections=("plugins",),
            fanout_collections=("plugins", "guide", "interface"),
            final_top_k=10,
            reranker_top_k=20,
        ),
        encoder=_Encoder(),
        sparse_encoder=_Sparse(),
        backend=_Backend(points),
        reranker=FlatReranker(),
        lookup_probe=_Lookup(lookup_ids, route="hit"),
    )
    result = runner.run([_case(lookup_route="hit")])[0]["strategies"]["rerank"]
    assert result["reranker_input_count"] == 20
    assert len(result["ordered_stable_ids"]) == 10
    assert any(
        stable_id not in result["reranker_input_stable_ids"]
        for stable_id in result["ordered_stable_ids"]
    )


def test_explicit_collection_filter_overrides_strategy_sets_for_every_strategy():
    backend = _Backend({"effects": [_point("fx", 0.9, effect_id="pixelate")]})
    runner = EvaluationRunner(
        config=EvaluationConfig(
            limited_collections=("plugins",),
            fanout_collections=("plugins", "ace"),
        ),
        encoder=_Encoder(),
        sparse_encoder=_Sparse(),
        backend=backend,
        reranker=_Reranker(),
        lookup_probe=_Lookup(route="bypass"),
    )
    row = runner.run(
        [
            _case(
                relevant=("effects|pixelate",),
                filters=ApiFilters(collections=("effects",)),
                lookup_route="bypass",
                api_route="semantic",
            )
        ]
    )[0]
    assert [call[0] for call in backend.calls] == ["effects"]
    assert all(result["collections"] == ["effects"] for result in row["strategies"].values())
    assert all(not result["filter_validation"]["violation_ids"] for result in row["strategies"].values())


def test_section_types_only_is_mandatory_and_validated_without_plugin():
    backend = _FilteringBackend(
        {
            "plugins": [
                _point(
                    "condition",
                    0.9,
                    source="plugin-reference/sprite.md",
                    h2_heading="Sprite conditions",
                    section_type="conditions",
                ),
                _point(
                    "action",
                    0.8,
                    source="plugin-reference/sprite.md",
                    h2_heading="Sprite actions",
                    section_type="actions",
                ),
            ]
        }
    )
    runner = EvaluationRunner(
        config=EvaluationConfig(
            strategies=("limited",),
            limited_collections=("plugins",),
            fanout_collections=("plugins",),
        ),
        encoder=_Encoder(),
        sparse_encoder=_Sparse(),
        backend=backend,
        lookup_probe=_Lookup(route="bypass"),
    )
    case = _case(
        relevant=("plugins|plugin-reference/sprite|sprite-conditions",),
        filters=ApiFilters(section_types=("conditions",)),
        lookup_route="bypass",
        api_route="semantic",
    )
    result = runner.run([case])[0]["strategies"]["limited"]
    assert result["ordered_stable_ids"] == [
        "plugins|plugin-reference/sprite|sprite-conditions"
    ]
    assert result["filter_validation"]["passes"]
    assert backend.calls[0][4].section_types == ("conditions",)


def test_filter_validation_audits_candidates_below_the_final_budget():
    runner = EvaluationRunner(
        config=EvaluationConfig(
            strategies=("limited",),
            limited_collections=("plugins",),
            fanout_collections=("plugins",),
            final_top_k=1,
        ),
        encoder=_Encoder(),
        sparse_encoder=_Sparse(),
        backend=_Backend(
            {
                "plugins": [
                    _point(
                        "condition",
                        0.9,
                        source="plugin-reference/sprite.md",
                        h2_heading="Sprite conditions",
                        section_type="conditions",
                    ),
                    _point(
                        "leaked-action",
                        0.1,
                        source="plugin-reference/sprite.md",
                        h2_heading="Sprite actions",
                        section_type="actions",
                    ),
                ]
            }
        ),
        lookup_probe=_Lookup(route="bypass"),
    )
    result = runner.run(
        [
            _case(
                filters=ApiFilters(section_types=("conditions",)),
                lookup_route="bypass",
                api_route="semantic",
            )
        ]
    )[0]["strategies"]["limited"]
    assert result["ordered_stable_ids"] == [
        "plugins|plugin-reference/sprite|sprite-conditions"
    ]
    assert not result["filter_validation"]["passes"]
    assert result["filter_validation"]["validated_candidate_count"] == 2


def test_live_qdrant_section_filter_uses_mandatory_match_any_when_dependency_exists():
    pytest.importorskip("qdrant_client")
    query_filter = LiveQdrantBackend._query_filter(
        ApiFilters(section_types=("conditions", "expressions"))
    )
    assert query_filter.should is None
    assert len(query_filter.must) == 1
    assert set(query_filter.must[0].match.any) == {"conditions", "expressions"}


def test_live_qdrant_contract_uses_named_dense_sparse_rrf_and_fixed_top10_pool():
    pytest.importorskip("qdrant_client")

    class Client:
        kwargs = None

        def query_points(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(points=[])

    backend = object.__new__(LiveQdrantBackend)
    backend.client = Client()
    result = backend.search(
        "plugins", [0.1, 0.2], {7: 0.8}, 10, ApiFilters()
    )
    request = backend.client.kwargs
    assert result.error is None
    assert request["collection_name"] == "c3_plugins"
    assert request["limit"] == 10
    assert [(item.using, item.limit) for item in request["prefetch"]] == [
        ("dense", 20),
        ("sparse", 20),
    ]
    assert request["query"].fusion.value == "rrf"


def test_negative_only_metrics_have_no_positive_denominator():
    metrics = evaluate_ranking(["effects|pixelate"], _case(relevant=()))
    assert metrics["negative_only"]
    assert metrics["hit_at"]["10"] is None
    assert metrics["recall_at"]["10"] is None
    assert metrics["mrr"] is None

    runner = EvaluationRunner(
        config=EvaluationConfig(
            strategies=("limited",),
            limited_collections=("effects",),
            fanout_collections=("effects",),
        ),
        encoder=_Encoder(),
        sparse_encoder=_Sparse(),
        backend=_Backend({"effects": [_point("fx", 0.9, effect_id="pixelate")]}),
        lookup_probe=_Lookup(),
    )
    rows = runner.run([_case(relevant=())])
    outcomes = stratified_summaries(rows, ("limited",))["limited"]["overall"][
        "negative_only_outcomes"
    ]
    assert outcomes["query_count"] == 1
    assert outcomes["returned_result_noise_count"] == 1
    assert outcomes["no_result_count"] == 0


def test_core_comparison_rejects_threshold_diversity_and_over_budget():
    with pytest.raises(ValueError, match="adaptive"):
        EvaluationConfig(
            strategies=("limited",), limited_collections=("plugins",), adaptive_threshold=True
        )
    with pytest.raises(ValueError, match="diversity"):
        EvaluationConfig(
            strategies=("limited",), limited_collections=("plugins",), diversity_injection=True
        )
    with pytest.raises(ValueError, match="hard cap"):
        EvaluationConfig(strategies=("limited",), limited_collections=("plugins",), final_top_k=11)


def test_paired_output_is_per_query_and_verifies_shared_digest():
    runner = EvaluationRunner(
        config=EvaluationConfig(
            limited_collections=("plugins",),
            fanout_collections=("plugins",),
        ),
        encoder=_Encoder(),
        sparse_encoder=_Sparse(),
        backend=_Backend(
            {"plugins": [_point("p", 0.9, source="plugin-reference/sprite.md", h2_heading="Sprite actions")]}
        ),
        reranker=_Reranker(),
        lookup_probe=_Lookup(),
    )
    rows = runner.run([_case()])
    paired = paired_comparisons(rows, runner.config.strategies)
    summaries = stratified_summaries(rows, runner.config.strategies)
    assert paired["rrf_vs_fanout"]["query_count"] == 1
    assert paired["rrf_vs_fanout"]["candidate_batch_digest_all_equal"]
    assert paired["rerank_vs_rrf"]["per_query"][0]["case_id"] == "semantic-test-01"
    latency = summaries["fanout"]["overall"]["latency"]["all"]
    assert set(("p50_ms", "p95_ms", "p99_ms", "max_ms")) <= set(latency)
