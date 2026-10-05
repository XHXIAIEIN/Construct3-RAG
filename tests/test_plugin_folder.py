"""plugin/, the Claude Code plugin: equal to a fresh build, under the directory's limits, and holding
every data and prompt file the skill's text sends an agent to (docs/decisions/plugin-folder.md)."""
import json
import os
import re
import subprocess
import sys

from tests.skill_helpers import REPO, SKILL

PLUGIN = REPO / "plugin"
NAMED = re.compile(r"Construct3-RAG/((?:data|prompts)/[A-Za-z0-9_./-]*[A-Za-z0-9_/])")


def test_plugin_folder_is_a_fresh_build_under_the_limits():
    p = subprocess.run([sys.executable, str(REPO / "scripts" / "build_plugin.py"), "--check"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr


def bundled(rel: str) -> bool:
    """A file the plugin keeps in a bundle beside its folder."""
    for bundle in PLUGIN.glob("data/**/*.bundle-*.json"):
        folder = bundle.relative_to(PLUGIN).as_posix().rsplit(".bundle-", 1)[0]
        if rel.startswith(folder + "/") and rel[len(folder) + 1:] in json.loads(bundle.read_text(encoding="utf-8")):
            return True
    return False


def test_every_data_and_prompt_file_the_skill_names_is_in_the_plugin():
    texts = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md")), SKILL / "assets" / "game-project-block.md"]
    missing, names = set(), 0
    for path in texts:
        for rel in NAMED.findall(path.read_text(encoding="utf-8")):
            names += 1
            if not ((PLUGIN / rel).exists() or bundled(rel)):
                missing.add(f"{path.name}: {rel}")
    assert names > 10 and not missing, sorted(missing)


def test_the_marketplace_installs_the_plugin_folder():
    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert [p["source"] for p in market["plugins"]] == ["./plugin"]
    assert not (REPO / ".claude-plugin" / "plugin.json").exists()
    assert json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["name"] == "construct3"


def test_scripts_in_the_plugin_read_the_bundled_data(tmp_path):
    scripts = PLUGIN / "skills" / "construct3-agent-plugin" / "scripts"
    # No CONSTRUCT3_RAG: the scripts find the plugin folder above them, as an installed plugin does
    env = {k: v for k, v in os.environ.items() if k != "CONSTRUCT3_RAG"}
    env.update(PYTHONIOENCODING="utf-8", CONSTRUCT3_RAG_OFFLINE="1")
    for args, expected in ((["lookup_script_api.py", "IRuntime.callFunction"],
                            "Construct3-RAG/data/c3-ts-defs/preview/interfaces/IRuntime.d.ts:"),
                           (["search_guides.py", "platformer"], "3d-platformer")):
        p = subprocess.run([sys.executable, str(scripts / args[0]), *args[1:]], cwd=tmp_path, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert p.returncode == 0 and expected in p.stdout, p.stdout + p.stderr
