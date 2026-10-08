"""advanced_random.py: the Advanced Random plugin in Python, and the --check that compares it with the runtime.

The pinned values were compared with the plugin's code by --check, against the c3runtime.js of an r504
Web export and the preview of the r505 editor, 2026-10-07.
"""
import json
import shutil
import sys

import pytest

from tests.skill_helpers import SKILL, run

sys.path.insert(0, str(SKILL / "scripts"))
import advanced_random as ar  # noqa: E402

SCRIPT = SKILL / "scripts" / "advanced_random.py"


def test_a_seed_gives_the_runtime_values():
    assert ar.seed_hash("ABCDEFGHIJ") == 842237596
    assert ar.seed_hash("种子🙂") == 3234365345     # charCodeAt counts UTF-16 units
    r = ar.AdvancedRandom("ABCDEFGHIJ")
    assert [r.random() for _ in range(3)] == [0.9818989339297937, 0.26031546714868026, 0.17583310838264643]
    r.table_from_json("t", json.dumps(ar.TABLE))
    assert [r.weighted_by_name("T") for _ in range(8)] == ["dango2", "dango2", "dango2", 7, "dango2", "dango2",
                                                           "dango1", "dango1"]
    r.create_permutation(9, 3)
    assert r.perm == [8, 10, 9, 5, 3, 4, 7, 6, 11]


def test_creating_a_table_draws_nothing_and_update_seed_starts_again():
    r = ar.AdvancedRandom("ABCDEFGHIJ")
    r.table_from_json("t", "[[1, 1]]")
    r.create_table("u")
    first = r.random()
    r.update_seed("ABCDEFGHIJ")
    assert first == r.random() == 0.9818989339297937


def test_the_command_prints_random_values_and_table_draws(tmp_path):
    code, out = run(tmp_path, SCRIPT, "ABCDEFGHIJ", "--count", "2")
    assert code == 0 and out.split() == ["0.9818989339297937", "0.26031546714868026"]
    code, out = run(tmp_path, SCRIPT, "ABCDEFGHIJ", "--table", json.dumps(ar.TABLE), "--count", "4")
    assert code == 0 and out.split() == ['7', '"dango1"', '"dango1"', '"dango2"']    # a text in quotes


def test_check_refuses_a_runtime_without_the_plugin(tmp_path):
    runtime = tmp_path / "c3runtime.js"
    runtime.write_text("// lib/misc/other.js\n{\nvar x = 1;\n}\n", encoding="utf-8")
    code, out = run(tmp_path, SCRIPT, "--check", "--runtime", str(runtime))
    if not shutil.which("node"):
        assert code == 2 and "no node" in out
        return
    assert code == 1 and "no longer has the shape this script reads" in out
    assert "plugins/AdvancedRandom/c3runtime/runtime.js" in out


@pytest.mark.skipif(not shutil.which("node"), reason="--check runs the plugin's code with node")
def test_check_names_what_the_plugin_no_longer_defines(tmp_path):
    """A stand-in plugin with the files the check reads and none of the actions it calls."""
    runtime = tmp_path / "c3runtime.js"
    runtime.write_text("// lib/misc/probability.js\n{\nself.C3.ProbabilityTable = class {};\n}\n\n"
                       "// scripts/plugins/AdvancedRandom/c3runtime/runtime.js\n{\nself.C3.Plugins.AdvancedRandom = {};\n}\n",
                       encoding="utf-8")
    code, out = run(tmp_path, SCRIPT, "--check", "--runtime", str(runtime))
    assert code == 1 and "no longer defines C3.Plugins.AdvancedRandom.Instance, NoiseFuncs.seed, Acts.SetSeed" in out
