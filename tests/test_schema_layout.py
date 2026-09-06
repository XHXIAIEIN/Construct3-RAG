import json
from pathlib import Path

from src.schema_layout import (
    SchemaManifest,
    load_locale_index,
    load_schema_manifest,
    schema_counts,
    schema_is_complete,
    select_schema_dir,
)


_NAMES = {
    "en-US": {"sprite": "Sprite", "platform": "Platform", "blur": "Blur"},
    "zh-CN": {"sprite": "精灵", "platform": "平台", "blur": "模糊"},
}


def _make_schema(root: Path, version: str = "r1") -> Path:
    entries = {
        "plugins": {"sprite": {"file": "plugins/sprite.json"}},
        "behaviors": {"platform": {"file": "behaviors/platform.json"}},
        "effects": {"blur": {"file": "effects/blur.json"}},
    }
    for locale in ("en-US", "zh-CN"):
        locale_index: dict = {"version": version, "language": locale}
        for addon_type, section in entries.items():
            directory = root / locale / addon_type
            directory.mkdir(parents=True, exist_ok=True)
            locale_index[addon_type] = {}
            for addon_id, entry in section.items():
                name = _NAMES[locale][addon_id]
                (directory / f"{addon_id}.json").write_text(
                    json.dumps({"id": addon_id, "name": name}, ensure_ascii=False),
                    encoding="utf-8",
                )
                locale_index[addon_type][addon_id] = {"name": name, "file": entry["file"]}
        (root / locale / "_index.json").write_text(
            json.dumps(locale_index, ensure_ascii=False),
            encoding="utf-8",
        )
    (root / "_index.json").write_text(
        json.dumps(
            {
                "version": version,
                "languages": ["en-US", "zh-CN"],
                **entries,
            }
        ),
        encoding="utf-8",
    )
    return root


def test_schema_is_complete_requires_bilingual_directories(tmp_path):
    root = tmp_path / "schemas"
    root.mkdir()
    (root / "_index.json").write_text("{}", encoding="utf-8")
    assert not schema_is_complete(root)
    assert schema_is_complete(_make_schema(root))


def test_schema_manifest_loader_returns_typed_contract(tmp_path):
    root = _make_schema(tmp_path / "schemas", "r9")

    manifest = load_schema_manifest(root)

    assert isinstance(manifest, SchemaManifest)
    assert manifest.version == "r9"
    assert manifest.counts == {"plugins": 1, "behaviors": 1, "effects": 1}
    assert manifest.plugins["sprite"].relative_file.as_posix() == "plugins/sprite.json"


def test_schema_is_complete_rejects_bad_manifest_json(tmp_path):
    root = _make_schema(tmp_path / "schemas")
    (root / "_index.json").write_text("{bad", encoding="utf-8")

    assert not schema_is_complete(root)


def test_schema_is_complete_rejects_missing_locale_file(tmp_path):
    root = _make_schema(tmp_path / "schemas")
    (root / "zh-CN" / "effects" / "blur.json").unlink()

    assert not schema_is_complete(root)


def test_schema_is_complete_rejects_bad_schema_json(tmp_path):
    root = _make_schema(tmp_path / "schemas")
    (root / "en-US" / "plugins" / "sprite.json").write_text("[", encoding="utf-8")

    assert not schema_is_complete(root)


def test_schema_is_complete_rejects_missing_locale_index(tmp_path):
    root = _make_schema(tmp_path / "schemas")
    (root / "zh-CN" / "_index.json").unlink()

    assert not schema_is_complete(root)


def test_schema_is_complete_rejects_locale_index_that_drifts_from_manifest(tmp_path):
    root = _make_schema(tmp_path / "schemas")
    path = root / "zh-CN" / "_index.json"
    locale_index = json.loads(path.read_text(encoding="utf-8"))
    locale_index["effects"] = {}
    path.write_text(json.dumps(locale_index), encoding="utf-8")

    assert not schema_is_complete(root)


def test_load_locale_index_returns_localized_names(tmp_path):
    root = _make_schema(tmp_path / "schemas")

    sections = load_locale_index(root, "zh-CN")

    assert set(sections) == {"plugins", "behaviors", "effects"}
    assert sections["plugins"]["sprite"] == {"name": "精灵", "file": "plugins/sprite.json"}
    assert sections["effects"]["blur"]["name"] == "模糊"


def test_effect_names_resolve_from_locale_indexes(tmp_path):
    """The root index no longer carries names, so lookup must read the locale ones."""
    from src.lookup.indexes import SchemaIndex

    index = SchemaIndex(_make_schema(tmp_path / "schemas"))

    assert index.find_effect_in_query("加一个模糊特效") == ("blur", 3, 5)
    assert index.find_effect_in_query("add blur effect") == ("blur", 4, 8)


def test_schema_is_complete_rejects_empty_manifest_section(tmp_path):
    root = _make_schema(tmp_path / "schemas")
    manifest = json.loads((root / "_index.json").read_text(encoding="utf-8"))
    manifest["effects"] = {}
    (root / "_index.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert not schema_is_complete(root)


def test_select_schema_dir_prefers_matching_generated_data(tmp_path):
    generated = _make_schema(tmp_path / "generated", "r2")
    bundled = _make_schema(tmp_path / "bundled", "r1")
    assert select_schema_dir(
        generated=generated,
        bundled=bundled,
        expected_version="r2",
    ) == generated


def test_select_schema_dir_falls_back_to_bundled_data(tmp_path):
    generated = tmp_path / "generated"
    bundled = _make_schema(tmp_path / "bundled", "r1")
    assert select_schema_dir(
        generated=generated,
        bundled=bundled,
        expected_version="r2",
    ) == bundled


def test_explicit_schema_dir_always_wins(tmp_path):
    explicit = tmp_path / "custom"
    assert select_schema_dir(
        generated=tmp_path / "generated",
        bundled=tmp_path / "bundled",
        expected_version="r2",
        explicit=explicit,
    ) == explicit


def test_schema_counts_uses_canonical_locale_names(tmp_path):
    root = _make_schema(tmp_path / "schemas")
    (root / "en-US" / "plugins" / "sprite.json").write_text("{}", encoding="utf-8")
    assert schema_counts(root)["plugins"] == 1


def test_bundled_schema_is_self_contained_and_loadable():
    """A clean checkout must not need the developer cache for Direct Lookup."""
    from src.lookup.indexes import SchemaIndex

    bundled = Path(__file__).parents[1] / "data" / "c3-schemas"
    assert schema_is_complete(bundled)

    index = SchemaIndex(bundled)
    resolved = index.resolve_name("Sprite")
    assert resolved == ("sprite", False)
    assert index.get_schema("sprite", is_behavior=False)
    assert index.find_effect_in_query("像素化") == ("pixellate", 0, 3)
    assert index.find_effect_in_query("Pixellate") == ("pixellate", 0, 9)
