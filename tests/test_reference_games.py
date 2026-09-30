from pathlib import Path

import pytest

from scripts.reference_games.catalog import CATALOG, load_catalog
from scripts.reference_games.decode import tween_single_properties


def test_reference_game_catalog_lives_in_the_ignored_workspace():
    assert ".local" in CATALOG.parts
    assert not (Path(__file__).resolve().parents[1] / "scripts" / "reference_games" / "catalog.json").exists()


def test_load_catalog_reads_the_given_list(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text('[{"source": "kind:a", "folder": "a", "author": "x"}]', encoding="utf-8")

    assert load_catalog(path) == [{"source": "kind:a", "folder": "a", "author": "x"}]


def test_load_catalog_without_a_list_says_where_it_belongs(tmp_path):
    with pytest.raises(SystemExit, match="not part of the repository"):
        load_catalog(tmp_path / "missing.json")


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
