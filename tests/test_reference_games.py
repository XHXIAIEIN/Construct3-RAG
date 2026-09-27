import json
from pathlib import Path

from scripts.reference_games.decode import tween_single_properties


REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "scripts" / "reference_games" / "catalog.json"


def test_reference_game_catalog_has_unique_sources_and_folders():
    entries = json.loads(CATALOG.read_text(encoding="utf-8"))

    assert len(entries) == 38
    assert all(set(entry) == {"source", "folder", "author"} for entry in entries)
    assert len({entry["source"] for entry in entries}) == len(entries)
    assert len({entry["folder"] for entry in entries}) == len(entries)
    assert all(entry["source"].startswith(("kind:", "kind:")) for entry in entries)
    assert all(entry["author"] for entry in entries)

    serialized = json.dumps(entries, ensure_ascii=False)
    assert "://" not in serialized
    assert "?" not in serialized
    assert "#" not in serialized
    assert "\\" not in serialized


def test_tween_property_order_comes_from_the_sampled_runtime(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "c3runtime.js").write_text(
        'const SINGLE_PROPERTIES=["offsetX","offsetY","offsetWidth",'
        '"offsetHeight","offsetAngle","offsetOpacity","offsetColor"];',
        encoding="utf-8",
    )

    assert tween_single_properties(tmp_path) == [
        "offsetX",
        "offsetY",
        "offsetWidth",
        "offsetHeight",
        "offsetAngle",
        "offsetOpacity",
        "offsetColor",
    ]
